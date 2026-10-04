use reqwest::blocking::{Client, Response};
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, HashMap},
    fs::{self, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::{Duration, Instant},
};
use tempfile::TempDir;

#[derive(Clone)]
pub struct Launch {
    pub program: PathBuf,
    pub arguments: Vec<String>,
}

pub struct Engine {
    pub root: PathBuf,
    child: Option<Child>,
    client: Client,
    url: String,
    token: String,
    local_token: String,
    inputs: Mutex<HashMap<String, PathBuf>>,
    _session: TempDir,
}

impl Engine {
    pub fn start(launch: &Launch, root: &Path, app_data: &Path) -> Result<Self, String> {
        let session = tempfile::Builder::new()
            .prefix("service-")
            .tempdir_in(app_data)
            .map_err(|_| "Cannot create a private service directory.")?;
        let ready = session.path().join("ready.json");
        let token = uuid::Uuid::new_v4().simple().to_string();
        let local_token = uuid::Uuid::new_v4().simple().to_string();
        let client = Client::builder()
            .no_proxy()
            .redirect(reqwest::redirect::Policy::none())
            .timeout(Duration::from_secs(15))
            .build()
            .map_err(|_| "Cannot create the local API client.")?;
        let mut command = Command::new(&launch.program);
        command
            .args(&launch.arguments)
            .arg("--state-dir")
            .arg(root)
            .args(["--port", "0", "--parent-stdin", "--ready-file"])
            .arg(&ready)
            .env("DICOMQC_API_TOKEN", &token)
            .env("DICOMQC_LOCAL_TOKEN", &local_token)
            .env_remove("PYTHONPATH")
            .env_remove("PYTHONHOME")
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let child = command
            .spawn()
            .map_err(|_| "Cannot launch the Python API. Check the desktop engine installation.")?;
        let mut engine = Self {
            inputs: Mutex::new(HashMap::new()),
            root: root.to_path_buf(),
            child: Some(child),
            client,
            url: String::new(),
            token,
            local_token,
            _session: session,
        };
        let deadline = Instant::now() + Duration::from_secs(30);
        while Instant::now() < deadline {
            if engine
                .child
                .as_mut()
                .unwrap()
                .try_wait()
                .map_err(|_| "Cannot inspect the API process.")?
                .is_some()
            {
                if let Ok(bytes) = fs::read(&ready) {
                    if let Ok(value) = serde_json::from_slice::<Value>(&bytes) {
                        if let Some(error) = value["error"].as_str() {
                            return Err(error.to_string());
                        }
                    }
                }
                return Err("The local API stopped during startup. Check that the workspace is available and not already open.".into());
            }
            if let Ok(bytes) = fs::read(&ready) {
                if let Ok(value) = serde_json::from_slice::<Value>(&bytes) {
                    if let Some(port) = value["port"]
                        .as_u64()
                        .filter(|port| (1..=65535).contains(port))
                    {
                        engine.url = format!("http://127.0.0.1:{port}");
                        let response = engine
                            .client
                            .get(format!("{}/api/v1/health", engine.url))
                            .bearer_auth(&engine.token)
                            .timeout(Duration::from_secs(1))
                            .send();
                        if let Ok(response) = response {
                            if response.status().is_success() {
                                let value: Value = response
                                    .json()
                                    .map_err(|_| "Invalid API health response.")?;
                                if value["version"] != env!("CARGO_PKG_VERSION")
                                    || value["api_version"] != 1
                                {
                                    return Err("The desktop and Python API versions do not match. Rebuild or reinstall the application.".into());
                                }
                                engine.root = root
                                    .canonicalize()
                                    .map_err(|_| "Cannot resolve the workspace.")?;
                                return Ok(engine);
                            }
                        }
                    }
                }
            }
            std::thread::sleep(Duration::from_millis(80));
        }
        Err("The local API did not become ready within 30 seconds.".into())
    }

    fn response(
        &self,
        path: &str,
        method: &str,
        body: &Value,
        privileged: bool,
    ) -> Result<Response, String> {
        let method =
            reqwest::Method::from_bytes(method.as_bytes()).map_err(|_| "Invalid method.")?;
        let mut request = self
            .client
            .request(method, format!("{}{path}", self.url))
            .bearer_auth(&self.token);
        if path.starts_with("/api/v1/projects/") {
            request = request.timeout(Duration::from_secs(600));
        }
        if privileged {
            request = request.header("X-Dicomqc-Local", &self.local_token);
        }
        if !body.is_null() {
            request = request.json(body);
        }
        let response = request.send().map_err(|_| {
            "The local API is unavailable. Restart the application if this continues."
        })?;
        if !response.status().is_success() {
            let value: Value = response.json().unwrap_or(Value::Null);
            return Err(value["detail"]
                .as_str()
                .unwrap_or(
                    "The local API rejected this request. Check the selected inputs and options.",
                )
                .to_string());
        }
        Ok(response)
    }

    pub fn request(&self, path: &str, method: &str, body: &Value) -> Result<Value, String> {
        let mut bytes = Vec::new();
        self.response(path, method, body, false)?
            .take(16 * 1024 * 1024 + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| "Cannot read the API response.")?;
        if bytes.len() > 16 * 1024 * 1024 {
            return Err("The API response is too large to display.".into());
        }
        serde_json::from_slice(&bytes).map_err(|_| "Invalid API response.".into())
    }

    pub fn project_request(&self, operation: &str, body: &Value) -> Result<Value, String> {
        self.response(&format!("/api/v1/projects/{operation}/local"), "POST", body, true)?
            .json().map_err(|_| "Invalid project response.".into())
    }

    pub fn register(&self, path: &Path) -> Result<Value, String> {
        let path = path
            .canonicalize()
            .map_err(|_| "The selected input is unavailable.")?;
        let mut input: Value = self
            .response("/api/v1/inputs/local", "POST", &json!({"path": path}), true)?
            .json()
            .map_err(|_| "Invalid input registration response.")?;
        let id = input["id"]
            .as_str()
            .ok_or("Invalid input registration response.")?
            .to_string();
        input["display_path"] = Value::String(path.to_string_lossy().into_owned());
        self.inputs
            .lock()
            .map_err(|_| "Input selection is unavailable.")?
            .insert(id, path);
        Ok(input)
    }

    pub fn input_text(&self, id: &str, maximum: usize) -> Result<String, String> {
        let path = self
            .inputs
            .lock()
            .map_err(|_| "Input selection is unavailable.")?
            .get(id)
            .cloned()
            .ok_or("Select the policy file again.")?;
        if !path.is_file()
            || path.canonicalize().map_err(|_| "The selected policy is unavailable.")? != path
        {
            return Err("The selected policy is unavailable.".into());
        }
        let mut bytes = Vec::new();
        fs::File::open(path)
            .and_then(|file| file.take(maximum as u64 + 1).read_to_end(&mut bytes))
            .map_err(|_| "Cannot read the selected policy.")?;
        if bytes.len() > maximum {
            return Err("Policy files must not exceed 64 KiB.".into());
        }
        String::from_utf8(bytes).map_err(|_| "Policy files must contain UTF-8 text.".into())
    }

    pub fn policy_target_allowed(&self, target: &Path) -> Result<(), String> {
        if target.starts_with(&self.root) || self.root.starts_with(target) {
            return Err("Keep policy files separate from the output folder.".into());
        }
        let paths = self
            .inputs
            .lock()
            .map_err(|_| "Input selection is unavailable.")?;
        if paths
            .values()
            .filter(|path| path.is_dir())
            .any(|path| target.starts_with(path))
        {
            return Err("Keep policy files outside the selected DICOM folders.".into());
        }
        Ok(())
    }


    pub fn input_paths(
        &self,
        groups: &BTreeMap<String, Vec<String>>,
    ) -> Result<BTreeMap<String, Vec<PathBuf>>, String> {
        let inputs = self
            .inputs
            .lock()
            .map_err(|_| "Input selection is unavailable.")?;
        groups
            .iter()
            .map(|(group, ids)| {
                let paths = ids
                    .iter()
                    .map(|id| {
                        inputs.get(id).cloned().ok_or_else(|| {
                            "Select the input again before saving the project.".into()
                        })
                    })
                    .collect::<Result<Vec<_>, String>>()?;
                Ok((group.clone(), paths))
            })
            .collect()
    }

    pub fn register_paths(
        &self,
        groups: &BTreeMap<String, Vec<PathBuf>>,
    ) -> Result<(Value, Vec<String>), String> {
        let mut registered = serde_json::Map::new();
        let mut missing = Vec::new();
        for (group, paths) in groups {
            let mut values = Vec::new();
            for path in paths {
                if !path.is_absolute() {
                    missing.push(path.to_string_lossy().into_owned());
                    continue;
                }
                match self.register(path) {
                    Ok(value) => values.push(value),
                    Err(_) => missing.push(path.to_string_lossy().into_owned()),
                }
            }
            registered.insert(group.clone(), Value::Array(values));
        }
        Ok((Value::Object(registered), missing))
    }

    pub fn delete_run(&self, id: &str) -> Result<(), String> {
        if !crate::protocol::valid_id(id) {
            return Err("Invalid run identifier.".into());
        }
        self.response(&format!("/api/v1/jobs/{id}"), "DELETE", &Value::Null, true)?;
        Ok(())
    }

    pub fn has_active(&self) -> Result<bool, String> {
        let jobs = self.request("/api/v1/jobs", "GET", &Value::Null)?;
        let jobs = jobs.as_array().ok_or("Invalid run list.")?;
        Ok(jobs
            .iter()
            .any(|job| matches!(job["status"].as_str(), Some("queued" | "running"))))
    }

    pub fn artifact_name(&self, id: &str, index: usize) -> Result<String, String> {
        if !crate::protocol::valid_id(id) {
            return Err("Invalid run identifier.".into());
        }
        let job = self.request(&format!("/api/v1/jobs/{id}"), "GET", &Value::Null)?;
        if job["status"] != "completed" {
            return Err("Reports are available after the audit completes.".into());
        }
        job["artifacts"]
            .as_array()
            .and_then(|items| items.get(index))
            .and_then(Value::as_str)
            .map(str::to_string)
            .ok_or("Report not found.".into())
    }

    pub fn preview(&self, id: &str, index: usize) -> Result<String, String> {
        let name = self.artifact_name(id, index)?;
        if ![".html", ".json", ".csv", ".yaml", ".yml"]
            .iter()
            .any(|extension| name.to_ascii_lowercase().ends_with(extension))
        {
            return Err("This report format cannot be previewed.".into());
        }
        let mut bytes = Vec::new();
        self.response(
            &format!("/api/v1/jobs/{id}/artifacts/{index}"),
            "GET",
            &Value::Null,
            false,
        )?
        .take(8 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "Cannot read the report.")?;
        if bytes.len() > 8 * 1024 * 1024 {
            return Err(
                "This report is too large for a preview. Save a copy to open it separately.".into(),
            );
        }
        String::from_utf8(bytes).map_err(|_| "The report is not valid UTF-8.".into())
    }

    pub fn export(&self, id: &str, index: usize, target: &Path) -> Result<(), String> {
        self.artifact_name(id, index)?;
        let mut response = self.response(
            &format!("/api/v1/jobs/{id}/artifacts/{index}"),
            "GET",
            &Value::Null,
            false,
        )?;
        // A report export must never overwrite an existing DICOM or other file.
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let mut file = options.open(target).map_err(|_| {
            "Choose a new filename in a writable folder; existing files are not overwritten."
        })?;
        let result = std::io::copy(&mut response, &mut file).and_then(|_| file.sync_all());
        drop(file);
        if result.is_err() {
            let _ = fs::remove_file(target);
            return Err("Could not save the complete report.".into());
        }
        Ok(())
    }

    pub fn export_job_record(&self, id: &str, target: &Path) -> Result<(), String> {
        if !crate::protocol::valid_id(id) {
            return Err("Invalid run identifier.".into());
        }
        let job = self.request(&format!("/api/v1/jobs/{id}"), "GET", &Value::Null)?;
        let record = json!({
            "format": "dicomqc-job-record",
            "version": 1,
            "id": job["id"],
            "name": job["name"],
            "created": job["created"],
            "mode": job["mode"],
            "example": job["example"],
            "status": job["status"],
            "audit_exit_code": job["audit_exit_code"],
            "summary": job["summary"],
            "parameters": job["parameters"],
            "policy": job["policy"],
            "log": job["log"],
        });
        let bytes =
            serde_json::to_vec_pretty(&record).map_err(|_| "Could not encode the job record.")?;
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let mut file = options.open(target).map_err(|_| {
            "Choose a new filename in a writable folder; existing files are not overwritten."
        })?;
        let result = file.write_all(&bytes).and_then(|_| file.sync_all());
        drop(file);
        if result.is_err() {
            let _ = fs::remove_file(target);
            return Err("Could not save the job record.".into());
        }
        Ok(())
    }

    pub fn run_directory(&self, id: &str) -> Result<PathBuf, String> {
        if !crate::protocol::valid_id(id) {
            return Err("Invalid run identifier.".into());
        }
        self.request(&format!("/api/v1/jobs/{id}"), "GET", &Value::Null)?;
        let directory = self.root.join(id).join("reports");
        if directory
            .canonicalize()
            .map_err(|_| "Run folder not available.")?
            != directory
            || !directory.is_dir()
        {
            return Err("Run folder changed or is unavailable.".into());
        }
        Ok(directory)
    }

    pub fn stop(&mut self) {
        let Some(mut child) = self.child.take() else {
            return;
        };
        if child.try_wait().ok().flatten().is_none() {
            if !self.url.is_empty() {
                let _ = self
                    .client
                    .post(format!("{}/api/v1/shutdown", self.url))
                    .bearer_auth(&self.token)
                    .header("X-Dicomqc-Local", &self.local_token)
                    .timeout(Duration::from_secs(2))
                    .send();
            }
            // EOF also supervises the API if HTTP shutdown fails.
            drop(child.stdin.take());
            let deadline = Instant::now() + Duration::from_secs(5);
            while Instant::now() < deadline {
                if child.try_wait().ok().flatten().is_some() {
                    return;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            let _ = child.kill();
        }
        let _ = child.wait();
    }
}

impl Drop for Engine {
    fn drop(&mut self) {
        self.stop();
    }
}

pub fn read_workspace(settings: &Path, default: &Path) -> Result<PathBuf, String> {
    if !settings.exists() {
        return Ok(default.to_path_buf());
    }
    let value: Value =
        serde_json::from_slice(&fs::read(settings).map_err(|_| "Cannot read workspace settings.")?)
            .map_err(|_| "Invalid workspace settings.")?;
    let path = PathBuf::from(
        value["workspace"]
            .as_str()
            .ok_or("Workspace setting is missing.")?,
    );
    if !path.is_absolute() {
        return Err("Workspace must be an absolute path.".into());
    }
    Ok(path)
}


pub fn write_workspace(settings: &Path, root: &Path) -> Result<(), String> {
    let parent = settings.parent().ok_or("Invalid settings location.")?;
    let mut file =
        tempfile::NamedTempFile::new_in(parent).map_err(|_| "Cannot save workspace settings.")?;
    file.write_all(
        serde_json::to_string(&json!({"workspace": root}))
            .unwrap()
            .as_bytes(),
    )
    .and_then(|_| file.as_file().sync_all())
    .map_err(|_| "Cannot save workspace settings.")?;
    file.persist(settings)
        .map_err(|_| "Cannot save workspace settings.")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn settings_survive_restart_and_reject_relative_paths() {
        let root = tempfile::tempdir().unwrap();
        let file = root.path().join("settings.json");
        let default = root.path().join("runs");
        assert_eq!(read_workspace(&file, &default).unwrap(), default);
        let chosen = root.path().join("other");
        write_workspace(&file, &chosen).unwrap();
        assert_eq!(read_workspace(&file, &default).unwrap(), chosen);
        fs::write(&file, r#"{"workspace":"relative"}"#).unwrap();
        assert!(read_workspace(&file, &default).is_err());
        fs::write(&file, "invalid").unwrap();
        assert!(read_workspace(&file, &default).is_err());
    }


    #[test]
    #[ignore = "requires the bundled Python engine and loopback networking"]
    fn bundled_api_bridge_examples_exports_and_restart() {
        let python = std::env::var_os("DICOMQC_TEST_PYTHON");
        let program = python.clone().or_else(|| std::env::var_os("DICOMQC_TEST_ENGINE"))
            .expect("Set DICOMQC_TEST_ENGINE or DICOMQC_TEST_PYTHON");
        let launch = Launch {
            program: if python.is_some() {PathBuf::from(program)} else {PathBuf::from(program).canonicalize().unwrap()},
            arguments: if python.is_some() {vec!["-m".into(), "dicomqc.api.server".into()]} else {vec![]},
        };
        let data = tempfile::tempdir().unwrap();
        let root = data.path().join("runs");
        let mut engine = Engine::start(&launch, &root, data.path()).unwrap();
        assert!(!engine.has_active().unwrap());
        let input = data.path().join("selected.dcm");
        fs::write(&input, "unchanged input").unwrap();
        let handle = engine.register(&input).unwrap();
        assert!(handle["id"].as_str().is_some());
        let input_ids = vec![handle["id"].as_str().unwrap().to_string()];
        let destination = data.path().join("other-runs");
        let mut replacement = Engine::start(&launch, &destination, data.path()).unwrap();
        let groups = BTreeMap::from([("paths".into(), input_ids)]);
        let paths = engine.input_paths(&groups).unwrap();
        let (transferred, missing) = replacement.register_paths(&paths).unwrap();
        assert!(missing.is_empty());
        let new_handle = &transferred["paths"][0];
        assert_ne!(new_handle["id"], handle["id"]);
        assert_eq!(
            new_handle["display_path"],
            input.canonicalize().unwrap().to_string_lossy().as_ref()
        );
        let mut transferred_job = replacement
            .request(
                "/api/v1/jobs",
                "POST",
                &json!({"mode": "scan", "inputs": {"paths": [new_handle["id"]]}, "options": {}}),
            )
            .unwrap();
        let transferred_id = transferred_job["id"].as_str().unwrap().to_string();
        let deadline = Instant::now() + Duration::from_secs(30);
        while matches!(
            transferred_job["status"].as_str(),
            Some("queued" | "running")
        ) {
            assert!(
                Instant::now() < deadline,
                "Transferred-input audit timed out"
            );
            std::thread::sleep(Duration::from_millis(80));
            transferred_job = replacement
                .request(
                    &format!("/api/v1/jobs/{transferred_id}"),
                    "GET",
                    &Value::Null,
                )
                .unwrap();
        }
        assert_eq!(transferred_job["status"], "completed");
        assert!(replacement
            .run_directory(&transferred_id)
            .unwrap()
            .starts_with(destination.canonicalize().unwrap()));
        assert_eq!(fs::read_to_string(&input).unwrap(), "unchanged input");
        replacement.stop();
        assert!(engine.register(&root).is_err());
        for example in ["scan", "compare", "policy", "uid", "vendor", "large"] {
            let mut job = engine
                .request(
                    "/api/v1/jobs",
                    "POST",
                    &json!({"mode":"demo", "example":example}),
                )
                .unwrap();
            let id = job["id"].as_str().unwrap().to_string();
            let deadline = Instant::now() + Duration::from_secs(30);
            while matches!(job["status"].as_str(), Some("queued" | "running")) {
                assert!(Instant::now() < deadline, "{example} audit timed out");
                std::thread::sleep(Duration::from_millis(80));
                job = engine
                    .request(&format!("/api/v1/jobs/{id}"), "GET", &Value::Null)
                    .unwrap();
            }
            assert_eq!(job["status"], "completed", "{job}");
            assert_eq!(
                job["audit_exit_code"],
                if example == "vendor" { 1 } else { 2 }
            );
            let index = job["artifacts"]
                .as_array()
                .unwrap()
                .iter()
                .position(|name| {
                    let name = name.as_str().unwrap();
                    name.ends_with(".html") && !name.ends_with("_mqc.html")
                })
                .unwrap();
            let html = engine.preview(&id, index).unwrap();
            assert!(html.contains("<html"));
            assert!(engine.run_directory(&id).unwrap().is_dir());
            let exported = data.path().join(format!("{example}.html"));
            engine.export(&id, index, &exported).unwrap();
            assert_eq!(fs::read_to_string(&exported).unwrap(), html);
            assert!(engine.export(&id, index, &input).is_err());
            assert_eq!(fs::read_to_string(&input).unwrap(), "unchanged input");
            assert!(engine.preview(&id, usize::MAX).is_err());
        }
        assert!(engine.run_directory("../escape").is_err());
        let saved_count = engine.request("/api/v1/jobs", "GET", &Value::Null).unwrap().as_array().unwrap().len();
        let package = data.path().join("Study.dicomqc");
        engine.project_request("save", &json!({"path": package, "project": {
            "format": "dicomqc-project", "version": 1, "mode": "scan", "inputs": {},
            "options": {"threads": 1, "uid_checks": false, "vendor_summary": false, "multiqc": false}
        }})).unwrap();
        let moved = data.path().join("Moved.dicomqc");
        fs::rename(package, &moved).unwrap();
        let imported = engine.project_request("open", &json!({"path": moved, "storage": data.path()})).unwrap();
        engine.stop();
        fs::remove_dir_all(&root).unwrap();
        let root = PathBuf::from(imported["output"].as_str().unwrap());
        let mut reopened = Engine::start(&launch, &root, data.path()).unwrap();
        assert_eq!(
            reopened
                .request("/api/v1/jobs", "GET", &Value::Null)
                .unwrap()
                .as_array()
                .unwrap()
                .len(),
            saved_count
        );
        let jobs = reopened
            .request("/api/v1/jobs", "GET", &Value::Null)
            .unwrap();
        let removed = jobs[0]["id"].as_str().unwrap();
        assert!(reopened.delete_run("../escape").is_err());
        assert!(reopened
            .request(&format!("/api/v1/jobs/{removed}"), "DELETE", &Value::Null)
            .is_err());
        reopened.delete_run(removed).unwrap();
        assert!(!root.join(removed).exists());
        assert_eq!(
            reopened
                .request("/api/v1/jobs", "GET", &Value::Null)
                .unwrap()
                .as_array()
                .unwrap()
                .len(),
            saved_count - 1
        );
        assert_eq!(fs::read_to_string(&input).unwrap(), "unchanged input");
        // Closing the native supervisor pipe must also stop the Python service.
        let mut child = reopened.child.take().unwrap();
        drop(child.stdin.take());
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            if let Some(status) = child.try_wait().unwrap() {
                assert!(status.success());
                break;
            }
            if Instant::now() >= deadline {
                let _ = child.kill();
                let _ = child.wait();
                panic!("API did not stop when its parent pipe closed");
            }
            std::thread::sleep(Duration::from_millis(80));
        }
    }
}

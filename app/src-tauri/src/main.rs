#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod engine;
mod protocol;
#[cfg(all(feature = "native-smoke", target_os = "linux"))]
mod smoke;

use engine::{Engine, Launch};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    collections::BTreeMap,
    fs,
    io::Write,
    path::{Path, PathBuf},
    process::Command,
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
};
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    Emitter, Manager,
};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons};

struct Desktop {
    engine: Mutex<Engine>,
    launch: Launch,
    data: PathBuf,
    settings: PathBuf,
    project_settings: PathBuf,
    project: Mutex<Option<PathBuf>>,
    quitting: AtomicBool,
    confirming: AtomicBool,
    dirty: AtomicBool,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ProjectDraft {
    mode: String,
    inputs: BTreeMap<String, Vec<String>>,
    options: ProjectOptions,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ProjectOptions {
    uid_checks: bool,
    vendor_summary: bool,
    multiqc: bool,
    #[serde(default = "default_threads")]
    threads: u16,
}

fn max_threads() -> u16 {
    u16::try_from(std::thread::available_parallelism().map_or(1, usize::from)).unwrap_or(u16::MAX)
}

fn default_threads() -> u16 {
    4.min(max_threads())
}

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ProjectFile {
    format: String,
    version: u8,
    output: PathBuf,
    mode: String,
    inputs: BTreeMap<String, Vec<PathBuf>>,
    options: ProjectOptions,
    #[serde(default)]
    saved_runs: Vec<Value>,
}

fn is_project_path(path: &Path) -> bool {
    path.extension().and_then(|value| value.to_str()) == Some("dicomqc")
}

fn write_project(path: &Path, project: &ProjectFile) -> Result<(), String> {
    if !is_project_path(path) || path.is_dir() {
        return Err("A dicomqc project must be a file ending in .dicomqc.".into());
    }
    let parent = path.parent().ok_or("Invalid project location.")?;
    fs::create_dir_all(parent).map_err(|_| "Cannot create the project location.")?;
    let bytes =
        serde_json::to_vec_pretty(project).map_err(|_| "Cannot encode the project file.")?;
    let mut file =
        tempfile::NamedTempFile::new_in(parent).map_err(|_| "Cannot create the project file.")?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        file.as_file()
            .set_permissions(fs::Permissions::from_mode(0o600))
            .map_err(|_| "Cannot protect the project file.")?;
    }
    file.write_all(&bytes)
        .and_then(|_| file.as_file().sync_all())
        .map_err(|_| "Cannot save the project file.")?;
    file.persist(path)
        .map_err(|_| "Cannot save the project file.")?;
    Ok(())
}

fn read_project(path: &Path) -> Result<ProjectFile, String> {
    if !is_project_path(path) || !path.is_file() || path.is_symlink() {
        return Err("Select a dicomqc project file ending in .dicomqc.".into());
    }
    let mut project: ProjectFile =
        serde_json::from_slice(&fs::read(path).map_err(|_| "This project file is not readable.")?)
            .map_err(|_| "The project file is invalid or uses unsupported fields.")?;
    if project.format != "dicomqc-project"
        || project.version != 1
        || !project.output.is_absolute()
        || !matches!(project.mode.as_str(), "scan" | "compare")
        || project.options.threads == 0
        || project.inputs.keys().any(|key| {
            !matches!(
                key.as_str(),
                "paths" | "source" | "candidate" | "manifest" | "policy"
            )
        })
    {
        return Err("This is not a supported dicomqc project.".into());
    }
    project.options.threads = project.options.threads.min(max_threads());
    Ok(project)
}

fn read_project_setting(path: &Path) -> Option<PathBuf> {
    let value: Value = serde_json::from_slice(&fs::read(path).ok()?).ok()?;
    let project = PathBuf::from(value["project"].as_str()?);
    (project.is_absolute() && project.is_file()).then_some(project)
}

fn write_project_setting(path: &Path, project: Option<&Path>) -> Result<(), String> {
    let parent = path.parent().ok_or("Invalid project settings location.")?;
    let mut file =
        tempfile::NamedTempFile::new_in(parent).map_err(|_| "Cannot save project settings.")?;
    let value = serde_json::json!({"project": project.map(|value| value.to_string_lossy())});
    file.write_all(value.to_string().as_bytes())
        .and_then(|_| file.as_file().sync_all())
        .map_err(|_| "Cannot save project settings.")?;
    file.persist(path)
        .map_err(|_| "Cannot save project settings.")?;
    Ok(())
}

fn project_response(
    project_path: Option<&Path>,
    project: &ProjectFile,
    inputs: Value,
    missing: Vec<String>,
) -> Value {
    serde_json::json!({
        "projectPath": project_path,
        "name": project_path.and_then(Path::file_stem).and_then(|value| value.to_str()).unwrap_or("Untitled"),
        "output": project.output,
        "project": {"mode": project.mode, "inputs": inputs, "options": project.options},
        "missing": missing,
        "savedJobs": project.saved_runs,
    })
}

fn with_engine<T>(
    app: &tauri::AppHandle,
    operation: impl FnOnce(&Engine) -> Result<T, String>,
) -> Result<T, String> {
    let state = app
        .try_state::<Desktop>()
        .ok_or("The local service is unavailable.")?;
    let engine = state
        .engine
        .lock()
        .map_err(|_| "The local service is unavailable.")?;
    operation(&engine)
}

#[tauri::command]
async fn api_request(
    app: tauri::AppHandle,
    path: String,
    method: String,
    body: Value,
) -> Result<Value, String> {
    if !protocol::allowed(&path, &method, &body) {
        return Err("This operation is not available to the desktop interface.".into());
    }
    tauri::async_runtime::spawn_blocking(move || {
        with_engine(&app, |engine| engine.request(&path, &method, &body))
    })
    .await
    .map_err(|_| "The service request could not finish.")?
}

#[tauri::command]
async fn select_input(app: tauri::AppHandle, directory: bool) -> Result<Option<Value>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let dialog = app.dialog().file().set_title(if directory {
            "Choose DICOM folder"
        } else {
            "Choose input file"
        });
        let selected = if directory {
            dialog.blocking_pick_folder()
        } else {
            dialog.blocking_pick_file()
        };
        let Some(selected) = selected else {
            return Ok(None);
        };
        let path = selected
            .into_path()
            .map_err(|_| "Choose a local filesystem path.")?
            .canonicalize()
            .map_err(|_| "The selected input is unavailable.")?;
        let mut input = with_engine(&app, |engine| engine.register(&path))?;
        input["display_path"] = Value::String(path.to_string_lossy().into_owned());
        Ok(Some(input))
    })
    .await
    .map_err(|_| "The file selection could not finish.")?
}

#[tauri::command]
fn read_policy(app: tauri::AppHandle, input_id: String) -> Result<String, String> {
    with_engine(&app, |engine| engine.input_text(&input_id, 64 * 1024))
}

fn write_policy_copy(target: &Path, text: &str) -> Result<(), String> {
    let parent = target.parent().ok_or("Invalid policy destination.")?;
    let mut staged = tempfile::NamedTempFile::new_in(parent)
        .map_err(|_| "Cannot create the policy file.")?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        staged
            .as_file()
            .set_permissions(fs::Permissions::from_mode(0o600))
            .map_err(|_| "Cannot protect the policy file.")?;
    }
    staged
        .write_all(text.as_bytes())
        .and_then(|_| staged.as_file().sync_all())
        .map_err(|_| "Cannot save the complete policy file.")?;
    staged.persist_noclobber(target).map_err(|_| {
        "Choose a new filename. Save as and use never overwrites an existing policy.".to_string()
    })?;
    Ok(())
}

#[tauri::command]
async fn save_policy_copy(app: tauri::AppHandle, text: String) -> Result<Option<Value>, String> {
    if text.is_empty() || text.len() > 64 * 1024 {
        return Err("Policy text must contain between 1 byte and 64 KiB.".into());
    }
    tauri::async_runtime::spawn_blocking(move || {
        with_engine(&app, |engine| {
            engine.request(
                "/api/v1/policies/validate",
                "POST",
                &serde_json::json!({"text": text}),
            )?;
            Ok(())
        })?;
        let Some(selected) = app
            .dialog()
            .file()
            .set_title("Save project policy")
            .set_file_name("dicomqc-policy.yaml")
            .add_filter("YAML policy", &["yaml", "yml"])
            .blocking_save_file()
        else {
            return Ok(None);
        };
        let mut target = selected
            .into_path()
            .map_err(|_| "Choose a local filesystem path.")?;
        if !matches!(target.extension().and_then(|value| value.to_str()), Some("yaml" | "yml")) {
            target.set_extension("yaml");
        }
        let parent = target
            .parent()
            .ok_or("Invalid policy destination.")?
            .canonicalize()
            .map_err(|_| "Choose an existing writable folder.")?;
        target = parent.join(target.file_name().ok_or("Invalid policy filename.")?);
        with_engine(&app, |engine| engine.policy_target_allowed(&target))?;
        write_policy_copy(&target, &text)?;
        with_engine(&app, |engine| engine.register(&target)).map(Some)
    })
    .await
    .map_err(|_| "The policy save could not finish.")?
}

#[tauri::command]
fn workspace(app: tauri::AppHandle) -> Result<String, String> {
    with_engine(&app, |engine| {
        Ok(engine.root.to_string_lossy().into_owned())
    })
}

#[tauri::command]
fn current_project(app: tauri::AppHandle) -> Result<Value, String> {
    let state = app.state::<Desktop>();
    let engine = state
        .engine
        .lock()
        .map_err(|_| "The local service is unavailable.")?;
    let path = state
        .project
        .lock()
        .map_err(|_| "Project state is unavailable.")?
        .clone();
    if let Some(path) = path {
        let project = read_project(&engine.root.with_extension("dicomqc"))?;
        let (inputs, missing) = engine.register_paths(&project.inputs)?;
        return Ok(project_response(Some(&path), &project, inputs, missing));
    }
    let project = ProjectFile {
        format: "dicomqc-project".into(),
        version: 1,
        saved_runs: Vec::new(),
        output: engine.root.clone(),
        mode: "scan".into(),
        inputs: BTreeMap::new(),
        options: ProjectOptions {
            uid_checks: false,
            vendor_summary: false,
            multiqc: false,
            threads: default_threads(),
        },
    };
    Ok(project_response(
        None,
        &project,
        serde_json::json!({}),
        Vec::new(),
    ))
}

#[tauri::command]
fn sync_menu(
    app: tauri::AppHandle,
    can_run: bool,
    can_cancel: bool,
    can_findings: bool,
    can_reports: bool,
    dirty: bool,
) -> Result<(), String> {
    app.state::<Desktop>().dirty.store(dirty, Ordering::SeqCst);
    let menu = app.menu().ok_or("Native menu is unavailable.")?;
    for entry in menu.items().map_err(|_| "Cannot update native menu.")? {
        if let Some(submenu) = entry.as_submenu() {
            for (id, enabled) in [
                ("run-audit", can_run),
                ("cancel-audit", can_cancel),
                ("log", can_findings),
                ("findings", can_findings),
                ("reports", can_reports),
            ] {
                if let Some(item) = submenu.get(id).and_then(|item| item.as_menuitem().cloned()) {
                    item.set_enabled(enabled)
                        .map_err(|_| "Cannot update native menu.")?;
                }
            }
        }
    }
    Ok(())
}

#[tauri::command]
async fn save_project(
    app: tauri::AppHandle,
    draft: Value,
    save_as: bool,
) -> Result<Option<Value>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let draft: ProjectDraft =
            serde_json::from_value(draft).map_err(|_| "The project settings are invalid.")?;
        if !matches!(draft.mode.as_str(), "scan" | "compare") {
            return Err("The project audit mode is invalid.".into());
        }
        if !(1..=max_threads()).contains(&draft.options.threads) {
            return Err(format!(
                "Metadata threads must be between 1 and {}.",
                max_threads()
            ));
        }
        let state = app
            .try_state::<Desktop>()
            .ok_or("The local service is unavailable.")?;
        let current = state
            .engine
            .lock()
            .map_err(|_| "The local service is unavailable.")?;
        let paths = current.input_paths(&draft.inputs)?;
        let project = ProjectFile {
            format: "dicomqc-project".into(),
            version: 1,
            saved_runs: serde_json::from_value(current.request("/api/v1/jobs", "GET", &Value::Null)?)
                .map_err(|_| "Cannot read run history.".to_string())?,
            output: current.root.clone(),
            mode: draft.mode,
            inputs: paths,
            options: draft.options,
        };
        let existing = state
            .project
            .lock()
            .map_err(|_| "Project state is unavailable.")?
            .clone();
        let target = if save_as || existing.is_none() {
            let Some(selected) = app
                .dialog()
                .file()
                .set_title("Save dicomqc project")
                .add_filter("dicomqc project", &["dicomqc"])
                .set_file_name("Untitled.dicomqc")
                .blocking_save_file()
            else {
                return Ok(None);
            };
            let mut path = selected
                .into_path()
                .map_err(|_| "Choose a local filesystem path.")?;
            if !is_project_path(&path) {
                path.set_extension("dicomqc");
            }
            path
        } else {
            existing.unwrap()
        };
        if current.has_active()? {
            return Err("Finish or cancel active audits before saving the project.".into());
        }
        if target.starts_with(&state.data) {
            return Err("Save the project outside dicomqc's internal application storage.".into());
        }
        current.project_request("save", &serde_json::json!({"path": target, "project": project}))?;
        write_project(&current.root.with_extension("dicomqc"), &project)?;
        write_project_setting(&state.project_settings, Some(&target))?;
        *state
            .project
            .lock()
            .map_err(|_| "Project state is unavailable.")? = Some(target.clone());
        Ok(Some(project_response(
            Some(&target),
            &project,
            Value::Null,
            Vec::new(),
        )))
    })
    .await
    .map_err(|_| "The project save could not finish.")?
}

#[tauri::command]
async fn open_project(app: tauri::AppHandle) -> Result<Option<Value>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let Some(selected) = app
            .dialog()
            .file()
            .set_title("Open dicomqc project")
            .add_filter("dicomqc project", &["dicomqc"])
            .blocking_pick_file()
        else {
            return Ok(None);
        };
        let path = selected
            .into_path()
            .map_err(|_| "Choose a local filesystem path.")?
            .canonicalize()
            .map_err(|_| "The selected project is unavailable.")?;
        if !app.dialog()
            .message("Open this project and allow dicomqc to read the external input paths recorded in it? Only open projects from sources you trust.")
            .title("Open project")
            .buttons(MessageDialogButtons::OkCancel)
            .blocking_show()
        {
            return Ok(None);
        }
        let state = app
            .try_state::<Desktop>()
            .ok_or("The local service is unavailable.")?;
        let mut current = state
            .engine
            .lock()
            .map_err(|_| "The local service is unavailable.")?;
        if current.has_active()? {
            return Err("Finish or cancel active audits before opening another project.".into());
        }
        let project: ProjectFile = serde_json::from_value(current.project_request("open", &serde_json::json!({"path": path, "storage": state.data}))?)
            .map_err(|_| "Invalid project metadata.".to_string())?;
        write_project(&project.output.with_extension("dicomqc"), &project)?;
        if current.root == project.output {
            let (inputs, missing) = current.register_paths(&project.inputs)?;
            write_project_setting(&state.project_settings, Some(&path))?;
            *state
                .project
                .lock()
                .map_err(|_| "Project state is unavailable.")? = Some(path.clone());
            return Ok(Some(project_response(
                Some(&path),
                &project,
                inputs,
                missing,
            )));
        }
        let replacement = Engine::start(&state.launch, &project.output, &state.data)?;
        let (inputs, missing) = replacement.register_paths(&project.inputs)?;
        engine::write_workspace(&state.settings, &replacement.root)?;
        write_project_setting(&state.project_settings, Some(&path))?;
        current.stop();
        *current = replacement;
        *state
            .project
            .lock()
            .map_err(|_| "Project state is unavailable.")? = Some(path.clone());
        Ok(Some(project_response(
            Some(&path),
            &project,
            inputs,
            missing,
        )))
    })
    .await
    .map_err(|_| "The project could not be opened.")?
}

#[tauri::command]
async fn new_project(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let state = app
            .try_state::<Desktop>()
            .ok_or("The local service is unavailable.")?;
        let mut current = state
            .engine
            .lock()
            .map_err(|_| "The local service is unavailable.")?;
        if current.has_active()? {
            return Err("Finish or cancel active audits before creating another project.".into());
        }
        let root = state.data.join(format!(
            "runs-{}",
            &uuid::Uuid::new_v4().simple().to_string()[..8]
        ));
        let replacement = Engine::start(&state.launch, &root, &state.data)?;
        let project = ProjectFile {
            format: "dicomqc-project".into(),
            version: 1,
            saved_runs: Vec::new(),
            output: replacement.root.clone(),
            mode: "scan".into(),
            inputs: BTreeMap::new(),
            options: ProjectOptions {
                uid_checks: false,
                vendor_summary: false,
                multiqc: false,
                threads: default_threads(),
            },
        };
        engine::write_workspace(&state.settings, &replacement.root)?;
        write_project_setting(&state.project_settings, None)?;
        current.stop();
        *current = replacement;
        *state
            .project
            .lock()
            .map_err(|_| "Project state is unavailable.")? = None;
        Ok(project_response(
            None,
            &project,
            serde_json::json!({}),
            Vec::new(),
        ))
    })
    .await
    .map_err(|_| "The new project could not be created.")?
}


#[tauri::command]
async fn read_report(app: tauri::AppHandle, id: String, index: usize) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || {
        with_engine(&app, |engine| engine.preview(&id, index))
    })
    .await
    .map_err(|_| "The preview could not finish.")?
}

#[tauri::command]
async fn save_report(app: tauri::AppHandle, id: String, index: usize) -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let name = with_engine(&app, |engine| engine.artifact_name(&id, index))?;
        let filename = Path::new(&name)
            .file_name()
            .and_then(|name| name.to_str())
            .ok_or("Invalid report filename.")?;
        let Some(selected) = app
            .dialog()
            .file()
            .set_title("Save report copy")
            .set_file_name(filename)
            .blocking_save_file()
        else {
            return Ok(false);
        };
        let target = selected
            .into_path()
            .map_err(|_| "Choose a local filesystem path.")?;
        with_engine(&app, |engine| engine.export(&id, index, &target))?;
        Ok(true)
    })
    .await
    .map_err(|_| "The export could not finish.")?
}

#[tauri::command]
async fn save_job_record(app: tauri::AppHandle, id: String) -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(move || {
        if !protocol::valid_id(&id) {
            return Err("Invalid run identifier.".into());
        }
        let filename = format!("dicomqc-job-{}.json", &id[..8]);
        let Some(selected) = app
            .dialog()
            .file()
            .set_title("Save job record")
            .set_file_name(filename)
            .blocking_save_file()
        else {
            return Ok(false);
        };
        let target = selected
            .into_path()
            .map_err(|_| "Choose a local filesystem path.")?;
        with_engine(&app, |engine| engine.export_job_record(&id, &target))?;
        Ok(true)
    })
    .await
    .map_err(|_| "The job-record export could not finish.")?
}

#[tauri::command]
async fn reveal_run(app: tauri::AppHandle, id: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let directory = with_engine(&app, |engine| engine.run_directory(&id))?;
        #[cfg(target_os = "linux")]
        let mut command = Command::new("xdg-open");
        #[cfg(target_os = "macos")]
        let mut command = Command::new("open");
        #[cfg(target_os = "windows")]
        let mut command = Command::new("explorer.exe");
        let mut child = command
            .arg(directory)
            .spawn()
            .map_err(|_| "Could not open the run folder.")?;
        std::thread::spawn(move || {
            let _ = child.wait();
        });
        Ok(())
    })
    .await
    .map_err(|_| "The folder could not be opened.")?
}

#[tauri::command]
async fn delete_run(app: tauri::AppHandle, id: String) -> Result<bool, String> {
    if !protocol::valid_id(&id) {
        return Err("Invalid run identifier.".into());
    }
    tauri::async_runtime::spawn_blocking(move || {
        let job = with_engine(&app, |engine| engine.request(&format!("/api/v1/jobs/{id}"), "GET", &Value::Null))?;
        if matches!(job["status"].as_str(), Some("queued" | "running")) {
            return Err("Finish or cancel this audit before deleting its run.".into());
        }
        if !app.dialog().message("Delete this run and its reports? Original input files will remain untouched. This cannot be undone.")
            .title("Delete run").buttons(MessageDialogButtons::OkCancel).blocking_show() {
            return Ok(false);
        }
        with_engine(&app, |engine| engine.delete_run(&id))?;
        Ok(true)
    }).await.map_err(|_| "Run deletion could not finish.")?
}

#[tauri::command]
async fn delete_runs(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let jobs = with_engine(&app, |engine| engine.request("/api/v1/jobs", "GET", &Value::Null))?;
        let identifiers: Vec<String> = jobs.as_array().ok_or("Invalid run list.")?.iter()
            .filter(|job| matches!(job["status"].as_str(), Some("completed" | "failed" | "cancelled" | "interrupted")))
            .filter_map(|job| job["id"].as_str().filter(|id| protocol::valid_id(id)).map(str::to_owned))
            .collect();
        if identifiers.is_empty() {
            return Ok(Vec::new());
        }
        let active = jobs.as_array().is_some_and(|values| values.iter()
            .any(|job| matches!(job["status"].as_str(), Some("queued" | "running"))));
        let message = if active {
            format!("Delete {} inactive runs and their reports? Active runs will remain. Original input files will remain untouched. This cannot be undone.", identifiers.len())
        } else {
            format!("Delete all {} runs and their reports? Original input files will remain untouched. This cannot be undone.", identifiers.len())
        };
        if !app.dialog().message(message).title("Delete all runs")
            .buttons(MessageDialogButtons::OkCancel).blocking_show() {
            return Ok(Vec::new());
        }
        for identifier in &identifiers {
            with_engine(&app, |engine| engine.delete_run(identifier))?;
        }
        Ok(identifiers)
    }).await.map_err(|_| "Run deletion could not finish.")?
}

#[tauri::command]
fn open_external(url: String) -> Result<(), String> {
    if ![
        "https://cnag-biomedical-informatics.github.io/dicomqc/",
        "https://github.com/CNAG-Biomedical-Informatics/dicomqc",
        "https://github.com/CNAG-Biomedical-Informatics/dicomqc/issues/new",
    ].contains(&url.as_str()) {
        return Err("This external link is not allowed.".into());
    }
    #[cfg(target_os = "linux")]
    let mut command = Command::new("xdg-open");
    #[cfg(target_os = "macos")]
    let mut command = Command::new("open");
    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = Command::new("rundll32.exe");
        command.arg("url.dll,FileProtocolHandler");
        command
    };
    let mut child = command.arg(url).spawn().map_err(|_| "Could not open the external link.")?;
    std::thread::spawn(move || { let _ = child.wait(); });
    Ok(())
}

fn request_exit(app: &tauri::AppHandle) {
    let Some(state) = app.try_state::<Desktop>() else {
        app.exit(0);
        return;
    };
    if state.confirming.swap(true, Ordering::SeqCst) {
        return;
    }
    let app = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let active = with_engine(&app, Engine::has_active).unwrap_or(true);
        let dirty = app.state::<Desktop>().dirty.load(Ordering::SeqCst);
        let verb = if cfg!(target_os = "windows") {
            "Exit"
        } else {
            "Quit"
        };
        let approved = (!active && !dirty) || app.dialog()
            .message(if active {
                format!("{verb} dicomqc and cancel active audits? Completed reports will remain in the output folder.")
            } else {
                format!("{verb} dicomqc and discard unsaved project changes?")
            })
            .title(if active { "Active audits" } else { "Unsaved project" }).buttons(MessageDialogButtons::OkCancel).blocking_show();
        let state = app.state::<Desktop>();
        if approved {
            state.quitting.store(true, Ordering::SeqCst);
            app.exit(0);
        }
        state.confirming.store(false, Ordering::SeqCst);
    });
}

fn launch_config(app: &tauri::App) -> Result<Launch, Box<dyn std::error::Error>> {
    if cfg!(debug_assertions) {
        if let Some(path) = std::env::var_os("DICOMQC_DESKTOP_ENGINE") {
            return Ok(Launch {
                program: path.into(),
                arguments: vec![],
            });
        }
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../..")
            .canonicalize()?;
        let program = std::env::var_os("DICOMQC_DESKTOP_PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                root.join(if cfg!(windows) {
                    ".venv/Scripts/python.exe"
                } else {
                    ".venv/bin/python"
                })
            });
        return Ok(Launch {
            program,
            arguments: vec!["-m".into(), "dicomqc.api.server".into()],
        });
    }
    Ok(Launch {
        program: app
            .path()
            .resource_dir()?
            .join("engine")
            .join(if cfg!(windows) {
                "dicomqc-api.exe"
            } else {
                "dicomqc-api"
            }),
        arguments: vec![],
    })
}

#[cfg(test)]
mod project_tests {
    use super::*;

    fn example() -> ProjectFile {
        ProjectFile {
            format: "dicomqc-project".into(),
            version: 1,
            saved_runs: Vec::new(),
            output: PathBuf::from("/tmp/dicomqc-runs"),
            mode: "scan".into(),
            inputs: BTreeMap::from([("paths".into(), vec![PathBuf::from("/data/study")])]),
            options: ProjectOptions {
                uid_checks: true,
                vendor_summary: false,
                multiqc: true,
                threads: 8,
            },
        }
    }

    #[test]
    fn project_manifest_round_trip_and_save_as() {
        let temporary = tempfile::tempdir().unwrap();
        let source = temporary.path().join("Study.dicomqc");
        write_project(&source, &example()).unwrap();

        let loaded = read_project(&source).unwrap();
        assert_eq!(loaded.mode, "scan");
        assert_eq!(loaded.inputs["paths"], [PathBuf::from("/data/study")]);
        assert_eq!(loaded.output, PathBuf::from("/tmp/dicomqc-runs"));
        assert!(loaded.options.uid_checks);
        assert_eq!(loaded.options.threads, 8.min(max_threads()));

        let target = temporary.path().join("Copy.dicomqc");
        write_project(&target, &loaded).unwrap();
        assert!(target.is_file());
        assert_eq!(read_project(&target).unwrap().output, loaded.output);
    }

    #[test]
    fn older_project_defaults_to_four_threads() {
        let temporary = tempfile::tempdir().unwrap();
        let project = temporary.path().join("Study.dicomqc");
        fs::write(&project, r#"{"format":"dicomqc-project","version":1,"output":"/tmp/runs","mode":"scan","inputs":{},"options":{"uid_checks":false,"vendor_summary":false,"multiqc":false}}"#).unwrap();

        assert_eq!(read_project(&project).unwrap().options.threads, default_threads());
    }

    #[test]
    fn project_manifest_rejects_wrong_extension_and_unknown_fields() {
        let temporary = tempfile::tempdir().unwrap();
        let wrong = temporary.path().join("Study");
        assert!(write_project(&wrong, &example()).is_err());

        let project = temporary.path().join("Study.dicomqc");
        fs::write(&project, r#"{"format":"dicomqc-project","version":1,"output":"/tmp/runs","mode":"scan","inputs":{},"options":{"uid_checks":false,"vendor_summary":false,"multiqc":false},"unexpected":true}"#).unwrap();
        assert!(read_project(&project).is_err());
    }

    #[test]
    fn policy_copy_is_private_and_never_overwrites() {
        let temporary = tempfile::tempdir().unwrap();
        let target = temporary.path().join("policy.yaml");
        write_policy_copy(&target, "version: 1\n").unwrap();
        assert_eq!(fs::read_to_string(&target).unwrap(), "version: 1\n");
        assert!(write_policy_copy(&target, "changed").is_err());
        assert_eq!(fs::read_to_string(&target).unwrap(), "version: 1\n");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(fs::metadata(&target).unwrap().permissions().mode() & 0o777, 0o600);
        }
    }
}

fn main() {
    #[cfg(target_os = "linux")]
    if !Path::new("/dev/dri").exists()
        && std::env::var_os("WEBKIT_DISABLE_COMPOSITING_MODE").is_none()
    {
        std::env::set_var("WEBKIT_DISABLE_COMPOSITING_MODE", "1");
    }
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let data = app.path().app_local_data_dir()?;
            #[cfg(all(feature = "native-smoke", target_os = "linux"))]
            let data = {
                let _ = data;
                smoke::directory().join("app-data")
            };
            std::fs::create_dir_all(&data)?;
            let settings = data.join("workspace.json");
            let project_settings = data.join("last-project.json");
            let configured = engine::read_workspace(&settings, &data.join("runs"))?;
            let project = read_project_setting(&project_settings)
                .and_then(|path| read_project(&configured.with_extension("dicomqc")).ok().map(|value| (path, value)));
            let root = project
                .as_ref()
                .map(|(_, value)| value.output.clone())
                .unwrap_or_else(|| {
                    if is_project_path(&configured) {
                        data.join("runs")
                    } else {
                        configured
                    }
                });
            let launch = launch_config(app)?;
            let engine = match Engine::start(&launch, &root, &data) {
                Ok(engine) => engine,
                Err(message) => {
                    let handle = app.handle().clone();
                    app.dialog()
                        .message(&message)
                        .title("Cannot start dicomqc")
                        .show(move |_| handle.exit(1));
                    return Ok(());
                }
            };
            engine::write_workspace(&settings, &engine.root)?;
            app.manage(Desktop {
                engine: Mutex::new(engine),
                launch,
                data,
                settings,
                project_settings,
                project: Mutex::new(project.map(|(path, _)| path)),
                quitting: AtomicBool::new(false),
                confirming: AtomicBool::new(false),
                dirty: AtomicBool::new(false),
            });
            let file = Submenu::with_items(
                app,
                "File",
                true,
                &[
                    &MenuItem::with_id(app, "new-project", "New Project", true, Some("CmdOrCtrl+N"))?,
                    &MenuItem::with_id(app, "open-project", "Open Project...", true, Some("CmdOrCtrl+O"))?,
                    &MenuItem::with_id(app, "save-project", "Save Project", true, Some("CmdOrCtrl+S"))?,
                    &MenuItem::with_id(app, "save-project-as", "Save Project As...", true, Some("CmdOrCtrl+Shift+S"))?,
                    &PredefinedMenuItem::separator(app)?,
                    &MenuItem::with_id(app, "new-audit", "New Audit", true, Some("CmdOrCtrl+Shift+N"))?,
                    &MenuItem::with_id(app, "add-file", "Add File...", true, None::<&str>)?,
                    &MenuItem::with_id(
                        app,
                        "add-folder",
                        "Add Folder...",
                        true,
                        None::<&str>,
                    )?,
                    &PredefinedMenuItem::separator(app)?,
                    &MenuItem::with_id(app, "quit", if cfg!(target_os = "windows") { "Exit" } else { "Quit" }, true, Some("CmdOrCtrl+Q"))?,
                ],
            )?;
            let edit = Submenu::with_items(
                app,
                "Edit",
                true,
                &[
                    &PredefinedMenuItem::undo(app, None)?,
                    &PredefinedMenuItem::redo(app, None)?,
                    &PredefinedMenuItem::separator(app)?,
                    &PredefinedMenuItem::cut(app, None)?,
                    &PredefinedMenuItem::copy(app, None)?,
                    &PredefinedMenuItem::paste(app, None)?,
                    &PredefinedMenuItem::select_all(app, None)?,
                ],
            )?;
            let view = Submenu::with_items(
                app,
                "View",
                true,
                &[
                    &MenuItem::with_id(app, "setup", "Audit Setup", true, Some("CmdOrCtrl+1"))?,
                    &MenuItem::with_id(app, "policy", "Project Policy", true, Some("CmdOrCtrl+4"))?,
                    &MenuItem::with_id(app, "findings", "Findings", true, Some("CmdOrCtrl+2"))?,
                    &MenuItem::with_id(app, "reports", "Reports", true, Some("CmdOrCtrl+3"))?,
                    &MenuItem::with_id(app, "log", "Job Log", false, Some("CmdOrCtrl+5"))?,
                    &PredefinedMenuItem::separator(app)?,
                    &MenuItem::with_id(app, "settings", "Settings", true, Some("CmdOrCtrl+,"))?,
                ],
            )?;
            let audit = Submenu::with_items(
                app,
                "Audit",
                true,
                &[&MenuItem::with_id(
                    app,
                    "run-audit",
                    "Run Audit",
                    true,
                    Some("CmdOrCtrl+Enter"),
                )?, &MenuItem::with_id(app, "cancel-audit", "Cancel Selected Audit", false, None::<&str>)?],
            )?;
            let help = Submenu::with_items(
                app,
                "Help",
                true,
                &[
                    &MenuItem::with_id(app, "documentation", "Documentation", true, None::<&str>)?,
                    &MenuItem::with_id(app, "report-issue", "Report an Issue...", true, None::<&str>)?,
                    &MenuItem::with_id(app, "about", "About dicomqc", true, None::<&str>)?,
                ],
            )?;
            app.set_menu(Menu::with_items(
                app,
                &[&file, &edit, &view, &audit, &help],
            )?)?;
            // Exercise the packaged executable, bundled engine, and setup hook in CI.
            if std::env::var_os("DICOMQC_DESKTOP_SMOKE_TEST").is_some() {
                app.state::<Desktop>().quitting.store(true, Ordering::SeqCst);
                println!("Desktop startup smoke test passed");
                app.handle().exit(0);
            }
            Ok(())
        })
        .on_menu_event(|app, event| match event.id().as_ref() {
            "quit" => request_exit(app),
            "documentation" => {
                #[cfg(target_os = "linux")]
                let mut command = Command::new("xdg-open");
                #[cfg(target_os = "macos")]
                let mut command = Command::new("open");
                #[cfg(target_os = "windows")]
                let mut command = {
                    let mut command = Command::new("rundll32.exe");
                    command.arg("url.dll,FileProtocolHandler");
                    command
                };
                if let Ok(mut child) = command
                    .arg("https://cnag-biomedical-informatics.github.io/dicomqc/")
                    .spawn()
                {
                    std::thread::spawn(move || {
                        let _ = child.wait();
                    });
                }
            }
            "about" => {
                app.dialog()
                    .message(format!(
                        "dicomqc {}\n\nDICOM metadata audits\nManuel Rueda, CNAG\nApache-2.0\n\nDICOM and reporting components\npydicom (requires 3.0+): DICOM metadata and tag dictionary\nPyYAML (requires 6+): project policies and YAML reports\nMultiQC (optional): viewer for exported QC reports\n\nExternal modification tools such as DCMTK are not bundled or invoked.",
                        env!("CARGO_PKG_VERSION")
                    ))
                    .title("About dicomqc")
                    .show(|_| {});
            }
            action => {
                let _ = app.emit_to("main", "desktop-menu", action);
            }
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window
                    .try_state::<Desktop>()
                    .is_some_and(|state| !state.quitting.load(Ordering::SeqCst))
                {
                    api.prevent_close();
                    request_exit(window.app_handle());
                }
            }
        });
    #[cfg(all(feature = "native-smoke", target_os = "linux"))]
    let builder = builder
        .on_page_load(|webview, payload| {
            if payload.event() == tauri::webview::PageLoadEvent::Finished {
                let _ = webview.eval(include_str!("../../tests/native-smoke.js"));
            }
        })
        .invoke_handler(tauri::generate_handler![
            api_request,
            select_input,
            read_policy,
            save_policy_copy,
            workspace,
            current_project,
            sync_menu,
            save_project,
            open_project,
            new_project,
            read_report,
            save_report,
            save_job_record,
            reveal_run,
            delete_run,
            delete_runs,
            open_external,
            smoke::smoke_checkpoint,
            smoke::smoke_finish
        ]);
    #[cfg(not(all(feature = "native-smoke", target_os = "linux")))]
    let builder = builder.invoke_handler(tauri::generate_handler![
        api_request,
        select_input,
        read_policy,
        save_policy_copy,
        workspace,
        current_project,
        sync_menu,
        save_project,
        open_project,
        new_project,
        read_report,
        save_report,
        save_job_record,
        reveal_run,
        delete_run,
        delete_runs,
        open_external
    ]);
    let app = builder.build(tauri::generate_context!());
    match app {
        Ok(app) => app.run(|app, event| {
            if let tauri::RunEvent::ExitRequested { api, .. } = &event {
                if app
                    .try_state::<Desktop>()
                    .is_some_and(|state| !state.quitting.load(Ordering::SeqCst))
                {
                    api.prevent_exit();
                    request_exit(app);
                }
            }
            if let tauri::RunEvent::Exit = event {
                if let Some(state) = app.try_state::<Desktop>() {
                    if let Ok(mut engine) = state.engine.lock() {
                        engine.stop();
                    }
                }
            }
        }),
        Err(_) => {
            eprintln!("Cannot start dicomqc desktop.");
            std::process::exit(1);
        }
    }
}

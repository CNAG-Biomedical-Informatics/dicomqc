#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod engine;
mod protocol;
#[cfg(all(feature = "native-smoke", target_os = "linux"))]
mod smoke;

use engine::{Engine, Launch};
use serde_json::Value;
use std::{
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
    quitting: AtomicBool,
    confirming: AtomicBool,
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
fn workspace(app: tauri::AppHandle) -> Result<String, String> {
    with_engine(&app, |engine| {
        Ok(engine.root.to_string_lossy().into_owned())
    })
}

#[tauri::command]
fn sync_menu(
    app: tauri::AppHandle,
    can_run: bool,
    can_findings: bool,
    can_reports: bool,
) -> Result<(), String> {
    let menu = app.menu().ok_or("Native menu is unavailable.")?;
    for entry in menu.items().map_err(|_| "Cannot update native menu.")? {
        if let Some(submenu) = entry.as_submenu() {
            for (id, enabled) in [
                ("run-audit", can_run),
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
async fn choose_workspace(
    app: tauri::AppHandle,
    input_ids: Vec<String>,
) -> Result<Option<Value>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let Some(selected) = app
            .dialog()
            .file()
            .set_title("Choose an output folder: empty or an existing dicomqc workspace")
            .blocking_pick_folder()
        else {
            return Ok(None);
        };
        let path = selected
            .into_path()
            .map_err(|_| "Choose a local filesystem path.")?
            .canonicalize()
            .map_err(|_| "The selected folder is unavailable.")?;
        let state = app
            .try_state::<Desktop>()
            .ok_or("The local service is unavailable.")?;
        let mut current = state
            .engine
            .lock()
            .map_err(|_| "The local service is unavailable.")?;
        if current.root == path {
            return Ok(None);
        }
        if current.has_active()? {
            return Err("Finish or cancel active audits before changing the workspace.".into());
        }
        if path.starts_with(&current.root) || current.root.starts_with(&path) {
            return Err("Choose a workspace separate from the current workspace.".into());
        }
        current.validate_output(&path, &input_ids)?;
        // Keep the original service usable until the replacement is ready and saved.
        let replacement = Engine::start(&state.launch, &path, &state.data)?;
        let inputs = current.transfer_inputs(&replacement, &input_ids)?;
        engine::write_workspace(&state.settings, &replacement.root)?;
        current.stop();
        *current = replacement;
        Ok(Some(
            serde_json::json!({"path": current.root, "inputs": inputs}),
        ))
    })
    .await
    .map_err(|_| "The workspace change could not finish.")?
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
        let approved = !active || app.dialog()
            .message("Quit dicomqc and cancel active audits? Completed reports will remain in the workspace.")
            .title("Active audits").buttons(MessageDialogButtons::OkCancel).blocking_show();
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
            let root = engine::read_workspace(&settings, &data.join("runs"))?;
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
            app.manage(Desktop {
                engine: Mutex::new(engine),
                launch,
                data,
                settings,
                quitting: AtomicBool::new(false),
                confirming: AtomicBool::new(false),
            });
            let file = Submenu::with_items(
                app,
                "File",
                true,
                &[
                    &MenuItem::with_id(app, "new-audit", "New Audit", true, Some("CmdOrCtrl+N"))?,
                    &MenuItem::with_id(app, "add-file", "Add File...", true, Some("CmdOrCtrl+O"))?,
                    &MenuItem::with_id(
                        app,
                        "add-folder",
                        "Add Folder...",
                        true,
                        Some("CmdOrCtrl+Shift+O"),
                    )?,
                    &PredefinedMenuItem::separator(app)?,
                    &PredefinedMenuItem::quit(app, None)?,
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
                    &MenuItem::with_id(app, "findings", "Findings", true, Some("CmdOrCtrl+2"))?,
                    &MenuItem::with_id(app, "reports", "Reports", true, Some("CmdOrCtrl+3"))?,
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
                )?],
            )?;
            let help = Submenu::with_items(
                app,
                "Help",
                true,
                &[
                    &MenuItem::with_id(app, "documentation", "Documentation", true, None::<&str>)?,
                    &MenuItem::with_id(app, "about", "About dicomqc", true, None::<&str>)?,
                ],
            )?;
            app.set_menu(Menu::with_items(
                app,
                &[&file, &edit, &view, &audit, &help],
            )?)?;
            Ok(())
        })
        .on_menu_event(|app, event| match event.id().as_ref() {
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
                        "dicomqc {}\n\nDICOM metadata audits\nManuel Rueda, CNAG\nApache-2.0",
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
            workspace,
            sync_menu,
            choose_workspace,
            read_report,
            save_report,
            reveal_run,
            delete_run,
            smoke::smoke_checkpoint,
            smoke::smoke_finish
        ]);
    #[cfg(not(all(feature = "native-smoke", target_os = "linux")))]
    let builder = builder.invoke_handler(tauri::generate_handler![
        api_request,
        select_input,
        workspace,
        sync_menu,
        choose_workspace,
        read_report,
        save_report,
        reveal_run,
        delete_run
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

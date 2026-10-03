//! Explicit opt-in Linux verification; excluded from normal desktop builds.
use serde_json::{json, Value};
use std::{path::PathBuf, sync::atomic::Ordering, time::Duration};
use tauri::Manager;
use webkit2gtk::WebViewExt;

pub fn directory() -> PathBuf {
    PathBuf::from(std::env::var_os("DICOMQC_SMOKE_DIR").expect("DICOMQC_SMOKE_DIR is required"))
}

#[tauri::command]
pub async fn smoke_checkpoint(
    app: tauri::AppHandle,
    label: String,
    details: Value,
) -> Result<(), String> {
    if label.is_empty()
        || label.len() > 48
        || !label
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'-')
    {
        return Err("Invalid checkpoint name".into());
    }
    let directory = directory();
    std::fs::create_dir_all(&directory).map_err(|e| e.to_string())?;
    let json_path = directory.join(format!("{label}.json"));
    std::fs::write(json_path, serde_json::to_vec_pretty(&details).unwrap())
        .map_err(|e| e.to_string())?;
    let window = app.get_webview_window("main").ok_or("Missing window")?;
    if let Some(width) = details["width"].as_f64() {
        window
            .set_size(tauri::LogicalSize::new(width, 900.0))
            .map_err(|e| e.to_string())?;
        return Ok(());
    }
    let target = directory.join(format!("{label}.png"));
    let (tx, rx) = std::sync::mpsc::channel();
    window
        .with_webview(move |webview| {
            webview.inner().snapshot(
                webkit2gtk::SnapshotRegion::Visible,
                webkit2gtk::SnapshotOptions::NONE,
                None::<&webkit2gtk::gio::Cancellable>,
                move |result| {
                    let saved = result.map_err(|e| e.to_string()).and_then(|surface| {
                        let mut file = std::fs::File::create(target).map_err(|e| e.to_string())?;
                        surface.write_to_png(&mut file).map_err(|e| e.to_string())
                    });
                    let _ = tx.send(saved);
                },
            );
        })
        .map_err(|e| e.to_string())?;
    tauri::async_runtime::spawn_blocking(move || {
        rx.recv_timeout(Duration::from_secs(10))
            .map_err(|e| e.to_string())?
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub fn smoke_finish(app: tauri::AppHandle, error: Option<String>) {
    let _ = std::fs::write(
        directory().join("result.json"),
        serde_json::to_vec_pretty(&json!({"success": error.is_none(), "error": error})).unwrap(),
    );
    app.state::<crate::Desktop>()
        .quitting
        .store(true, Ordering::SeqCst);
    app.exit(if error.is_none() { 0 } else { 1 });
}

use semver::Version;
use serde::Deserialize;
use std::time::Duration;

pub const DOWNLOADS: &str = "https://github.com/CNAG-Biomedical-Informatics/dicomqc/releases";
const ENDPOINT: &str =
    "https://api.github.com/repos/CNAG-Biomedical-Informatics/dicomqc/releases/latest";

#[derive(Deserialize)]
struct Release {
    tag_name: String,
    draft: bool,
    prerelease: bool,
}

fn version(value: &str) -> Result<Version, String> {
    Version::parse(value.strip_prefix('v').unwrap_or(value))
        .map_err(|_| "The release version could not be compared.".to_owned())
}

fn summary(current: &str, release: &Release) -> Result<String, String> {
    let installed = version(current)?;
    let published = version(&release.tag_name)?;
    if release.draft || release.prerelease || !published.pre.is_empty() {
        return Err("GitHub did not return a stable published release.".to_owned());
    }
    let result = if published > installed {
        "A newer release is available."
    } else if !installed.pre.is_empty() {
        "You are using a development build. No newer published release was found."
    } else {
        "No newer published release was found."
    };
    Ok(format!(
        "Desktop version: {current}\nLatest published release: {}\n\n{result}\n\nRelease notes and downloads:\n{DOWNLOADS}\n\nNo update has been downloaded or installed.",
        release.tag_name
    ))
}

pub fn check(current: &str) -> Result<String, String> {
    // This separate, user-initiated client sends no local engine credentials or audit data.
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(15))
        .user_agent("dicomqc-desktop-release-check")
        .build()
        .map_err(|_| "The update connection could not be initialized.".to_owned())?;
    let response = client
        .get(ENDPOINT)
        .header("Accept", "application/vnd.github+json")
        .send()
        .map_err(|_| "GitHub could not be reached. Check your internet connection.".to_owned())?;
    if response.status() == reqwest::StatusCode::NOT_FOUND {
        return Ok(format!("Desktop version: {current}\n\nNo public stable release is available yet.\n\nRelease notes and downloads:\n{DOWNLOADS}"));
    }
    let response = response.error_for_status().map_err(|error| {
        format!(
            "GitHub returned an error: {}",
            error
                .status()
                .map(|status| status.to_string())
                .unwrap_or_default()
        )
    })?;
    let release: Release = response
        .json()
        .map_err(|_| "GitHub returned an unreadable release response.".to_owned())?;
    summary(current, &release)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn release(tag: &str) -> Release {
        Release {
            tag_name: tag.to_owned(),
            draft: false,
            prerelease: false,
        }
    }

    #[test]
    fn compares_versions_numerically() {
        assert!(summary("0.9.0", &release("v0.10.0"))
            .unwrap()
            .contains("A newer"));
        assert!(summary("0.2.0", &release("v0.2.0"))
            .unwrap()
            .contains("No newer"));
        assert!(summary("0.2.0", &release("v0.1.0"))
            .unwrap()
            .contains("No newer"));
        assert!(summary("0.2.0-dev", &release("v0.2.0"))
            .unwrap()
            .contains("A newer"));
        assert!(summary("0.3.0-dev", &release("v0.2.0"))
            .unwrap()
            .contains("development build"));
    }

    #[test]
    fn rejects_unpublished_and_invalid_versions() {
        let mut candidate = release("v0.3.0");
        candidate.draft = true;
        assert!(summary("0.2.0", &candidate).is_err());
        candidate.draft = false;
        candidate.prerelease = true;
        assert!(summary("0.2.0", &candidate).is_err());
        assert!(summary("0.2.0", &release("v0.3.0-rc.1")).is_err());
        assert!(summary("0.2.0", &release("invalid")).is_err());
        assert!(summary("invalid", &release("v0.2.0")).is_err());
    }
}

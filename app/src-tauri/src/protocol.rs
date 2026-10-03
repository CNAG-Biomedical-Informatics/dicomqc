use serde_json::Value;

pub fn valid_id(value: &str) -> bool {
    value.len() == 32
        && value
            .bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}

/// Only user-facing operations may cross the renderer boundary.
pub fn allowed(path: &str, method: &str, body: &Value) -> bool {
    if path.len() > 256 || (!matches!(method, "POST" | "PATCH") && !body.is_null()) {
        return false;
    }
    if method == "GET"
        && matches!(
            path,
            "/api/v1/health" | "/api/v1/capabilities" | "/api/v1/jobs"
        )
    {
        return true;
    }
    if method == "POST" && path == "/api/v1/jobs" {
        return body.is_object();
    }
    if method == "POST" && path == "/api/v1/policies/validate" {
        return body.as_object().is_some_and(|value| {
            value.len() == 1
                && value["text"]
                    .as_str()
                    .is_some_and(|text| !text.is_empty() && text.len() <= 64 * 1024)
        });
    }
    let Some(suffix) = path.strip_prefix("/api/v1/jobs/") else {
        return false;
    };
    let (id, rest) = suffix.split_once('/').unwrap_or((suffix, ""));
    if !valid_id(id) {
        return false;
    }
    if method == "POST" {
        return rest == "cancel" && body.is_null();
    }
    if method == "PATCH" {
        return rest.is_empty()
            && body
                .as_object()
                .is_some_and(|value| value.len() == 1 && value["name"].is_string());
    }
    if method != "GET" {
        return false;
    }
    if rest.is_empty() || rest == "results" {
        return true;
    }
    let Some(query) = rest.strip_prefix("results?") else {
        return false;
    };
    let mut seen = std::collections::HashSet::new();
    for pair in query.split('&') {
        let Some((key, raw)) = pair.split_once('=') else {
            return false;
        };
        if !seen.insert(key) || raw.is_empty() || !raw.bytes().all(|c| c.is_ascii_digit()) {
            return false;
        }
        let Ok(value) = raw.parse::<u64>() else {
            return false;
        };
        if !matches!(key, "offset" | "limit") || (key == "limit" && !(1..=500).contains(&value)) {
            return false;
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn permits_audit_operations() {
        let root = format!("/api/v1/jobs/{}", "a".repeat(32));
        for path in [
            "/api/v1/health",
            "/api/v1/capabilities",
            "/api/v1/jobs",
            &root,
            &format!("{root}/results?offset=100&limit=100"),
        ] {
            assert!(allowed(path, "GET", &Value::Null), "{path}");
        }
        assert!(allowed("/api/v1/jobs", "POST", &json!({"mode":"demo"})));
        assert!(allowed(
            "/api/v1/policies/validate",
            "POST",
            &json!({"text": "version: 1"})
        ));
        assert!(allowed(&format!("{root}/cancel"), "POST", &Value::Null));
        assert!(allowed(&root, "PATCH", &json!({"name": "Baseline audit"})));
    }

    #[test]
    fn rejects_privileged_routes_and_encoded_escapes() {
        for path in [
            "/api/v1/shutdown",
            "/api/v1/inputs/local",
            "http://evil.example",
            "//evil.example",
            "/api/v1/jobs/../shutdown",
            "/api/v1/jobs/%2e%2e/shutdown",
            "/api/v1/jobs?x=1",
        ] {
            assert!(!allowed(path, "GET", &Value::Null));
            assert!(!allowed(path, "POST", &json!({})));
        }
        let root = format!("/api/v1/jobs/{}/results?", "a".repeat(32));
        for query in [
            "",
            "offset=-1",
            "limit=0",
            "limit=501",
            "limit=1&limit=2",
            "x=1",
            "offset=%30",
            "offset=1#x",
        ] {
            assert!(
                !allowed(&format!("{root}{query}"), "GET", &Value::Null),
                "{query}"
            );
        }
        assert!(!allowed("/api/v1/jobs", "DELETE", &Value::Null));
        assert!(!allowed("/api/v1/jobs", "GET", &json!({})));
        assert!(!allowed(
            &root,
            "PATCH",
            &json!({"name": "x", "extra": true})
        ));
        assert!(!allowed(
            "/api/v1/policies/validate",
            "POST",
            &json!({"text": "", "extra": true})
        ));
    }
}

import Foundation
import WidgetKit

struct WidgetSession: Codable, Equatable, Identifiable {
    var id: String
    var title: String
    var project: String
    var status: String
    var summary: String
    var startedAt: Double
    var provider: String? = nil
    var tokenCount: Int? = nil
    var weeklyUsedPercent: Double? = nil

    static func parse(_ entries: [[String: Any]]) -> [WidgetSession] {
        entries.compactMap { entry in
            guard let id = entry["sessionId"] as? String else { return nil }
            let title = ["title", "name", "project"].compactMap { entry[$0] as? String }
                .first(where: { !$0.isEmpty }) ?? "セッション"
            let question = entry["question"] as? String ?? ""
            let response = entry["lastResponse"] as? String ?? ""
            let detail = entry["detail"] as? String ?? ""
            let tool = entry["currentTool"] as? String ?? ""
            let summary = !question.isEmpty ? question : (!response.isEmpty ? response : (!tool.isEmpty ? tool : detail))
            return WidgetSession(id: id, title: String(title.prefix(120)),
                                 project: entry["project"] as? String ?? "",
                                 status: entry["status"] as? String ?? "idle",
                                 summary: String(summary.prefix(2000)),
                                 startedAt: entry["startedAt"] as? Double ?? 0,
                                 provider: entry["provider"] as? String,
                                 tokenCount: entry["tokenCount"] as? Int,
                                 weeklyUsedPercent: entry["weeklyUsedPercent"] as? Double)
        }.sorted {
            let left = rank($0.status), right = rank($1.status)
            if left != right { return left < right }
            if $0.startedAt != $1.startedAt { return $0.startedAt > $1.startedAt }
            return $0.id < $1.id
        }
    }

    private static func rank(_ status: String) -> Int {
        switch status {
        case "question", "permission": return 0
        case "working", "compacting": return 1
        case "waiting": return 2
        default: return 3
        }
    }
}

struct SessionWidgetSnapshot: Codable {
    var sessions: [WidgetSession]
    var updatedAt: Date?
}

enum SessionWidgetStore {
    static let group = "group.com.tento.ClaudeLive"
    static let kind = "ClaudeLiveSessions"
    private static var defaults: UserDefaults? { UserDefaults(suiteName: group) }

    static func snapshot() -> SessionWidgetSnapshot {
        guard let data = defaults?.data(forKey: "sessionSnapshot"),
              let result = try? JSONDecoder().decode(SessionWidgetSnapshot.self, from: data)
        else { return SessionWidgetSnapshot(sessions: [], updatedAt: nil) }
        return result
    }

    /// Called by the app; the extension gets only this app group's connection settings.
    static func syncConnection() {
        for key in ["manualHost", "lastDaemonURL", "lastServiceName", "daemonAuthToken"] {
            defaults?.set(UserDefaults.standard.string(forKey: key) ?? "", forKey: key)
        }
    }

    static var pushToken: String? { defaults?.string(forKey: "widgetPushToken") }

    static func setPushToken(_ token: String) {
        defaults?.set(token, forKey: "widgetPushToken")
    }

    static func setDeviceName(_ name: String) {
        defaults?.set(name, forKey: "widgetDeviceName")
    }

    /// Persist first: if token generation precedes pairing, registration retries on refresh.
    static func registerPushToken() async {
        guard let pushToken, let device = defaults?.string(forKey: "widgetDeviceName"),
              !device.isEmpty,
              let body = try? JSONSerialization.data(withJSONObject: [
                "device": device, "widgetPushToken": pushToken
              ]) else { return }
        _ = await request(path: "/register", method: "POST", body: body)
    }

    private static func request(path: String, method: String = "GET", body: Data? = nil) async -> Data? {
        let settings = defaults
        let token = settings?.string(forKey: "daemonAuthToken") ?? ""
        let manual = settings?.string(forKey: "manualHost") ?? ""
        let scheme = manual.lowercased().hasPrefix("https://") ? "https" : "http"
        var hosts = [manual.isEmpty ? "" : "\(scheme)://\(normalizedManualHostPort(manual))",
                     settings?.string(forKey: "lastDaemonURL") ?? ""]
        if let service = settings?.string(forKey: "lastServiceName"), !service.isEmpty {
            hosts.append("http://\(service).local:53536")
        }
        let urls = Array(Set(hosts.filter { !$0.isEmpty }.compactMap { host -> URL? in
            let base = sanitizeDaemonURL(host)
            guard let url = URL(string: base), let scheme = url.scheme,
                  ["http", "https"].contains(scheme), url.host != nil else { return nil }
            return URL(string: base + path)
        }))
        return await withTaskGroup(of: Data?.self) { group in
            for url in urls {
                group.addTask {
                    var request = URLRequest(url: url, timeoutInterval: 5)
                    request.httpMethod = method
                    request.httpBody = body
                    if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
                    if !token.isEmpty { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
                    guard let (data, response) = try? await URLSession.shared.data(for: request),
                          (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
                    return data
                }
            }
            for await result in group {
                if let result { group.cancelAll(); return result }
            }
            return nil
        }
    }

    static func save(_ entries: [[String: Any]], reload: Bool = true) -> SessionWidgetSnapshot {
        let previous = snapshot()
        let result = SessionWidgetSnapshot(sessions: WidgetSession.parse(entries), updatedAt: Date())
        if let data = try? JSONEncoder().encode(result) { defaults?.set(data, forKey: "sessionSnapshot") }
        if reload && (previous.sessions != result.sessions || previous.updatedAt == nil
                      || Date().timeIntervalSince(previous.updatedAt!) > 15 * 60) {
            WidgetCenter.shared.reloadTimelines(ofKind: kind)
        }
        return result
    }

    static func refresh() async -> (snapshot: SessionWidgetSnapshot, connected: Bool) {
        await registerPushToken()
        guard let data = await request(path: "/sessions"),
              let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              object["ok"] as? Bool == true,
              let entries = object["sessions"] as? [[String: Any]] else {
            return (snapshot(), false)
        }
        return (save(entries, reload: false), true)
    }
}

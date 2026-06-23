import Supabase
import Foundation

// The Supabase anon (publishable) key is injected into the generated Info.plist
// at build time from Secrets.xcconfig (git-ignored) and read here at runtime, so
// it never lives in source control. See Secrets.xcconfig.example for setup.
//
// The project URL is intentionally left in source — it isn't a secret (the
// project ref is already public), and `//` in a URL breaks xcconfig parsing.
private func requireInfoValue(_ key: String) -> String {
    let value = Bundle.main.object(forInfoDictionaryKey: key) as? String ?? ""
    guard !value.isEmpty, value != "$(\(key))" else {
        fatalError("""
        Missing \(key). Copy frontend/Secrets.xcconfig.example to \
        frontend/Secrets.xcconfig and fill in your Supabase anon key.
        """)
    }
    return value
}

let supabase = SupabaseClient(
    supabaseURL: URL(string: "https://homeympykewfrsifkpbb.supabase.co")!,
    supabaseKey: requireInfoValue("SUPABASE_ANON_KEY")
)

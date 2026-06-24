import SwiftUI

@main
struct dimple_frontendApp: App {
    @State private var auth = AuthViewModel()

    var body: some Scene {
        WindowGroup {
            Group {
                if auth.isAuthenticated {
                    ContentView()
                } else {
                    AuthView()
                }
            }
            .environment(auth)
            .animation(.easeInOut(duration: 0.35), value: auth.isAuthenticated)
        }
    }
}

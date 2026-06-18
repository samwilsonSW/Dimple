import Foundation
import AuthenticationServices
import Supabase

struct AppUser {
    let id: String
    let email: String?
    let displayName: String?

    init(from user: User) {
        self.id    = user.id.uuidString
        self.email = user.email
        if case .string(let name) = user.userMetadata["display_name"] {
            self.displayName = name
        } else {
            self.displayName = nil
        }
    }
}

@Observable
class AuthViewModel {
    var currentUser: AppUser?
    var isLoading: Bool    = false
    var errorMessage: String?

    var isAuthenticated: Bool { currentUser != nil }

    init() {
        Task {
            // Restore session that survived app restart (stored in Keychain by supabase-swift)
            if let session = try? await supabase.auth.session {
                await MainActor.run {
                    self.currentUser = AppUser(from: session.user)
                }
            }

            // Keep auth state in sync with server (token refresh, remote sign-out, etc.)
            for await (event, session) in await supabase.auth.authStateChanges {
                await MainActor.run {
                    switch event {
                    case .signedIn, .tokenRefreshed, .userUpdated:
                        if let user = session?.user {
                            self.currentUser = AppUser(from: user)
                        }
                    case .signedOut:
                        self.currentUser  = nil
                        self.errorMessage = nil
                    default:
                        break
                    }
                }
            }
        }
    }

    // MARK: - Sign In with Apple
    // Requires: "Sign in with Apple" capability + Apple Developer account
    func handleAppleSignIn(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData   = credential.identityToken,
                  let token       = String(data: tokenData, encoding: .utf8) else { return }
            Task {
                await run {
                    try await supabase.auth.signInWithIdToken(
                        credentials: .init(provider: .apple, idToken: token)
                    )
                }
            }
        case .failure(let error):
            errorMessage = error.localizedDescription
        }
    }

    // MARK: - Sign In with Google
    // Requires: GoogleSignIn-iOS package + Supabase Google OAuth configured
    func signInWithGoogle() {
        // TODO:
        //   GIDSignIn.sharedInstance.signIn(withPresenting: rootVC) { result, error in
        //       guard let idToken = result?.user.idToken?.tokenString else { return }
        //       try await supabase.auth.signInWithIdToken(
        //           credentials: .init(provider: .google, idToken: idToken)
        //       )
        //   }
        errorMessage = "Google Sign-In requires the GoogleSignIn-iOS package and Supabase OAuth setup."
    }

    // MARK: - Email / Password Sign In
    func signIn(email: String, password: String) async {
        await run {
            try await supabase.auth.signIn(email: email, password: password)
        }
    }

    // MARK: - Email / Password Sign Up
    func signUp(email: String, password: String, name: String) async {
        await run {
            var metadata: [String: AnyJSON] = [:]
            if !name.isEmpty { metadata["display_name"] = .string(name) }
            try await supabase.auth.signUp(email: email, password: password, data: metadata)
        }
    }

    // MARK: - Sign Out
    func signOut() {
        Task {
            try? await supabase.auth.signOut()
            // authStateChanges listener above handles clearing currentUser
        }
    }

    // MARK: - Private

    private func run(_ block: @escaping () async throws -> Void) async {
        await MainActor.run {
            isLoading    = true
            errorMessage = nil
        }
        do {
            try await block()
        } catch {
            await MainActor.run { self.errorMessage = error.localizedDescription }
        }
        await MainActor.run { isLoading = false }
    }
}

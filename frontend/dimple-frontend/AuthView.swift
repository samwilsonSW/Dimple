import SwiftUI
import AuthenticationServices

struct AuthView: View {
    @Environment(AuthViewModel.self) private var auth
    @Environment(\.colorScheme) private var colorScheme

    @State private var isSignUp    = false
    @State private var name        = ""
    @State private var email       = ""
    @State private var password    = ""
    @State private var confirmPass = ""
    @FocusState private var focusedField: Field?

    private enum Field: Hashable { case name, email, password, confirmPass }

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                brandHeader
                    .padding(.top, 60)
                    .padding(.bottom, 44)

                formSection
                    .padding(.horizontal, 28)

                togglePrompt
                    .padding(.top, 20)
                    .padding(.bottom, 40)
            }
        }
        .background(Color(.systemBackground))
        .scrollDismissesKeyboard(.interactively)
        .animation(.spring(response: 0.4, dampingFraction: 0.8), value: isSignUp)
    }

    // MARK: Brand Header

    private var brandHeader: some View {
        VStack(spacing: 14) {
            Circle()
                .fill(Color.forestGreen)
                .frame(width: 72, height: 72)
                .overlay {
                    Image(systemName: "figure.golf")
                        .font(.system(size: 34))
                        .foregroundStyle(.white)
                }
                .shadow(color: Color.forestGreen.opacity(0.3), radius: 16, y: 6)

            Text("Dimple")
                .font(.system(size: 40, weight: .bold, design: .rounded))
                .foregroundStyle(Color(.label))

            Text("Your AI Golf Coach")
                .font(.subheadline)
                .foregroundStyle(Color(.secondaryLabel))
        }
    }

    // MARK: Form Section

    private var formSection: some View {
        VStack(spacing: 14) {
            // Social sign-in
            SignInWithAppleButton(.signIn) { request in
                request.requestedScopes = [.fullName, .email]
            } onCompletion: { result in
                auth.handleAppleSignIn(result)
            }
            .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
            .frame(height: 52)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

            googleButton

            divider

            // Name field (sign up only)
            if isSignUp {
                inputField("Full Name", text: $name, icon: "person", field: .name)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }

            inputField("Email", text: $email, icon: "envelope", field: .email)
                .keyboardType(.emailAddress)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()

            inputField("Password", text: $password, icon: "lock", field: .password, isSecure: true)

            if isSignUp {
                inputField("Confirm Password", text: $confirmPass, icon: "lock.rotation", field: .confirmPass, isSecure: true)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }

            // Error
            if let error = auth.errorMessage {
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    Text(error)
                        .font(.footnote)
                        .foregroundStyle(Color(.secondaryLabel))
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.orange.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .transition(.opacity)
            }

            primaryButton
        }
    }

    // MARK: Google Button

    private var googleButton: some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            auth.signInWithGoogle()
        } label: {
            HStack(spacing: 10) {
                // Google "G" mark (color-coded manually since SF Symbols has no Google icon)
                ZStack {
                    Circle()
                        .fill(Color(.systemBackground))
                        .frame(width: 22, height: 22)
                    Text("G")
                        .font(.system(size: 14, weight: .bold, design: .rounded))
                        .foregroundStyle(Color(red: 66/255, green: 133/255, blue: 244/255))
                }
                Text("Continue with Google")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(Color(.label))
            }
            .frame(maxWidth: .infinity)
            .frame(height: 52)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(Color(.separator), lineWidth: 0.5)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: Divider

    private var divider: some View {
        HStack(spacing: 12) {
            Rectangle()
                .fill(Color(.separator))
                .frame(height: 0.5)
            Text("or continue with email")
                .font(.caption)
                .foregroundStyle(Color(.tertiaryLabel))
                .fixedSize()
            Rectangle()
                .fill(Color(.separator))
                .frame(height: 0.5)
        }
        .padding(.vertical, 4)
    }

    // MARK: Input Field

    private func inputField(
        _ placeholder: String,
        text: Binding<String>,
        icon: String,
        field: Field,
        isSecure: Bool = false
    ) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.subheadline)
                .foregroundStyle(Color(.tertiaryLabel))
                .frame(width: 20)

            Group {
                if isSecure {
                    SecureField(placeholder, text: text)
                } else {
                    TextField(placeholder, text: text)
                }
            }
            .font(.body)
            .focused($focusedField, equals: field)
            .onSubmit { advanceFocus(from: field) }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 14)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(
                    focusedField == field ? Color.forestGreen.opacity(0.5) : Color.clear,
                    lineWidth: 1.5
                )
        )
        .animation(.easeInOut(duration: 0.15), value: focusedField == field)
    }

    // MARK: Primary Button

    private var primaryButton: some View {
        let label = isSignUp ? "Create Account" : "Sign In"
        let isValid = isSignUp
            ? !email.isEmpty && !password.isEmpty && password == confirmPass
            : !email.isEmpty && !password.isEmpty

        return Button {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            focusedField = nil
            Task {
                if isSignUp {
                    await auth.signUp(email: email, password: password, name: name)
                } else {
                    await auth.signIn(email: email, password: password)
                }
            }
        } label: {
            ZStack {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(isValid ? Color.forestGreen : Color(.systemFill))
                    .frame(height: 52)

                if auth.isLoading {
                    ProgressView()
                        .tint(.white)
                } else {
                    Text(label)
                        .font(.body)
                        .fontWeight(.semibold)
                        .foregroundStyle(isValid ? .white : Color(.tertiaryLabel))
                }
            }
        }
        .disabled(!isValid || auth.isLoading)
        .animation(.spring(response: 0.3, dampingFraction: 0.7), value: isValid)
        .padding(.top, 4)
    }

    // MARK: Toggle Prompt

    private var togglePrompt: some View {
        Button {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                isSignUp.toggle()
                name = ""
                password = ""
                confirmPass = ""
            }
        } label: {
            HStack(spacing: 4) {
                Text(isSignUp ? "Already have an account?" : "Don't have an account?")
                    .foregroundStyle(Color(.secondaryLabel))
                Text(isSignUp ? "Sign In" : "Sign Up")
                    .foregroundStyle(Color.forestGreen)
                    .fontWeight(.semibold)
            }
            .font(.subheadline)
        }
        .buttonStyle(.plain)
    }

    // MARK: Focus Chain

    private func advanceFocus(from field: Field) {
        switch field {
        case .name:        focusedField = .email
        case .email:       focusedField = .password
        case .password:    focusedField = isSignUp ? .confirmPass : nil
        case .confirmPass: focusedField = nil
        }
    }
}

#Preview {
    AuthView()
        .environment(AuthViewModel())
}

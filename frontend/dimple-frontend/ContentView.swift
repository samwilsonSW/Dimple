//
//  ContentView.swift
//  dimple-frontend
//
//  Created by Sam Wilson on 6/1/26.
//

import SwiftUI

struct ContentView: View {
    @State private var showWelcome = !HandicapStore.shared.hasOnboarded

    var body: some View {
        TabView {
            NavigationStack {
                CoachView()
            }
            .tabItem {
                Label("Coach", systemImage: "bubble.left.and.text.bubble.right")
            }

            NewRoundView()
                .tabItem {
                    Label("New Round", systemImage: "flag.fill")
                }
        }
        .tint(.forestGreen)
        .fullScreenCover(isPresented: $showWelcome) {
            NavigationStack {
                HandicapSetupView(mode: .welcome) { showWelcome = false }
            }
        }
    }
}

#Preview {
    ContentView()
}

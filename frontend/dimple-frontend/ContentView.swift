//
//  ContentView.swift
//  dimple-frontend
//
//  Created by Sam Wilson on 6/1/26.
//

import SwiftUI

struct ContentView: View {
    enum Tab: Hashable { case coach, newRound, history }

    @State private var selection: Tab = .coach
    @State private var showWelcome = !HandicapStore.shared.hasOnboarded

    var body: some View {
        TabView(selection: $selection) {
            NavigationStack {
                CoachView()
            }
            .tag(Tab.coach)
            .tabItem {
                Label("Coach", systemImage: "bubble.left.and.text.bubble.right")
            }

            NewRoundView()
                .tag(Tab.newRound)
                .tabItem {
                    Label("New Round", systemImage: "flag.fill")
                }

            RoundHistoryView(onNewRound: { selection = .newRound })
                .tag(Tab.history)
                .tabItem {
                    Label("History", systemImage: "list.bullet.rectangle.portrait")
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

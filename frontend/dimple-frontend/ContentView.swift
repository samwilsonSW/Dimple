//
//  ContentView.swift
//  dimple-frontend
//
//  Created by Sam Wilson on 6/1/26.
//

import SwiftUI

struct ContentView: View {
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
    }
}

#Preview {
    ContentView()
}

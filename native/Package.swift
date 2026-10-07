// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "WixalNative", platforms: [.macOS(.v14)],
    products: [.executable(name: "WixalNative", targets: ["WixalNative"])],
    dependencies: [
        .package(url: "https://github.com/migueldeicaza/SwiftTerm.git", exact: "1.20.0"),
        .package(url: "https://github.com/swiftlang/swift-markdown.git", exact: "0.9.0")
    ],
    targets: [
        .target(name: "WixalActivity", path: "ActivitySources"),
        .target(name: "WixalMarkdown", dependencies: [.product(name: "Markdown", package: "swift-markdown")], path: "MarkdownSources"),
        .executableTarget(name: "WixalNative", dependencies: ["SwiftTerm", "WixalMarkdown", "WixalActivity"], path: "Sources"),
        .executableTarget(name: "ActivityAcceptance", dependencies:["WixalActivity"], path:"ActivityChecks"),
        .executableTarget(name: "MarkdownAcceptance", dependencies: ["WixalMarkdown"], path: "SwiftTests")
    ]
)

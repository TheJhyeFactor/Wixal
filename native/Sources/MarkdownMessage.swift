import SwiftUI
import AppKit
import WixalMarkdown

struct MarkdownMessage:View{
    let content:String
    var body:some View{MarkdownBlocksView(blocks:markdownBlocks(content)).environment(\.openURL,OpenURLAction{url in NSPasteboard.general.clearContents();NSPasteboard.general.setString(url.absoluteString,forType:.string);return .handled})}
}
private struct MarkdownBlocksView:View{
    let blocks:[MarkdownBlock]
    @Environment(\.wixalTheme) private var theme
    @Environment(\.wixalTextSize) private var textSize
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var body:some View{
        VStack(alignment:.leading,spacing:14){
            ForEach(blocks){block in
                switch block.kind{
                case "heading":SwiftUI.Text(inlineMarkdown(block.text)).font(.system(size:block.level==1 ? 24 : block.level==2 ? 20 : 16,weight:.semibold)).padding(.top,8).textSelection(.enabled)
                case "code":
                    VStack(alignment:.leading,spacing:0){HStack{SwiftUI.Text(block.language.isEmpty ? "Code" : block.language);Spacer();Button("Copy"){copyText(block.text)}.buttonStyle(.plain)}.font(.system(size:10,design:.monospaced)).foregroundStyle(theme.muted).padding(.horizontal,14).padding(.vertical,10);Rectangle().fill(theme.line).frame(height:1);ScrollView(.horizontal){SwiftUI.Text(highlightCode(block.text)).font(.system(size:max(11,textSize-2),design:.monospaced)).lineSpacing(5).textSelection(.enabled).padding(16).frame(maxWidth:.infinity,alignment:.leading)}}.background(theme.inset,in:RoundedRectangle(cornerRadius:9)).overlay(RoundedRectangle(cornerRadius:9).stroke(theme.line,lineWidth:1))
                case "table":
                    ResponseTable(rows:block.rows,theme:theme,fontSize:max(12,textSize-1),alignments:block.alignments).accessibilityLabel("Response table")
                case "list":AnyView(MarkdownBlocksView(blocks:block.children))
                case "item":
                    HStack(alignment:.top,spacing:10){SwiftUI.Text(block.marker).foregroundStyle(theme.muted).frame(minWidth:18,alignment:.trailing);AnyView(MarkdownBlocksView(blocks:block.children)).frame(maxWidth:.infinity,alignment:.leading)}
                case "quote":
                    HStack(alignment:.top,spacing:12){Rectangle().fill(theme.accent.opacity(0.5)).frame(width:3);AnyView(MarkdownBlocksView(blocks:block.children)).frame(maxWidth:.infinity,alignment:.leading)}.fixedSize(horizontal:false,vertical:true).padding(.vertical,3)
                case "html":SwiftUI.Text(block.text).font(.system(size:max(11,textSize-2),design:.monospaced)).textSelection(.enabled)
                case "rule":Rectangle().fill(theme.line).frame(height:1).padding(.vertical,5)
                default:SwiftUI.Text(inlineMarkdown(block.text)).font(.system(size:textSize)).lineSpacing(6).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)
                }
            }
        }.foregroundStyle(theme.text).tint(theme.accent).frame(maxWidth:.infinity,alignment:.leading)
            .animation(reduceMotion ? nil : .easeOut(duration:0.16),value:blocks.count)
    }
    private func highlightCode(_ code:String)->AttributedString{
        var value=AttributedString(code)
        let expressions:[(String,Color)]=[("\\b(func|let|var|if|else|return|class|struct|import|from|def|async|await|for|while|const|function|public|private|true|false|null|None|self)\\b",theme.accent),("(?m)//[^\\n]*|#[^\\n]*",theme.muted),("\"[^\"\\n]*\"|'[^'\\n]*'",theme.accent.opacity(0.8))]
        for (pattern,color) in expressions{guard let regex=try? NSRegularExpression(pattern:pattern) else{continue};for match in regex.matches(in:code,range:NSRange(code.startIndex...,in:code)){guard let range=Range(match.range,in:code),let lower=AttributedString.Index(range.lowerBound,within:value),let upper=AttributedString.Index(range.upperBound,within:value) else{continue};value[lower..<upper].foregroundColor=color}}
        return value
    }
    private func copyText(_ value:String){NSPasteboard.general.clearContents();NSPasteboard.general.setString(value,forType:.string)}
}

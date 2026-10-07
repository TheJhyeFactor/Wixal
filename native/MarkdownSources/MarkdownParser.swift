import Foundation
import AppKit
import Markdown

public struct MarkdownBlock:Identifiable {
    public let id:Int
    public let kind:String
    public let text:String
    public var language:String=""
    public var rows:[[String]]=[]
    public var level:Int=1
    public var marker:String=""
    public var children:[MarkdownBlock]=[]
    public var alignments:[NSTextAlignment]=[]
}
public func markdownBlocks(_ content:String)->[MarkdownBlock] {
    let document=Markdown.Document(parsing:content)
    func convert(_ nodes:MarkupChildren)->[MarkdownBlock] {
        nodes.enumerated().map { index,node in
            if let code=node as? Markdown.CodeBlock {
                return MarkdownBlock(id:index,kind:"code",text:code.code,language:code.language ?? "")
            }
            if let heading=node as? Markdown.Heading {
                return MarkdownBlock(id:index,kind:"heading",text:heading.children.map{$0.detachedFromParent.format()}.joined(),level:heading.level)
            }
            if let table=node as? Markdown.Table {
                let rows=[Array(table.head.cells.map{$0.children.map{$0.detachedFromParent.format()}.joined()})]+table.body.rows.map{row in Array(row.cells.map{$0.children.map{$0.detachedFromParent.format()}.joined()})}
                let alignments=table.columnAlignments.map { value -> NSTextAlignment in
                    switch value { case .center:return .center;case .right:return .right;default:return .left }
                }
                return MarkdownBlock(id:index,kind:"table",text:"",rows:rows,alignments:alignments)
            }
            if node is Markdown.ThematicBreak { return MarkdownBlock(id:index,kind:"rule",text:"") }
            if node is Markdown.BlockQuote {
                return MarkdownBlock(id:index,kind:"quote",text:"",children:convert(node.children))
            }
            if node is Markdown.UnorderedList || node is Markdown.OrderedList {
                let first=(node as? Markdown.OrderedList)?.startIndex
                let items=node.children.enumerated().map { offset,item in
                    let checkbox=(item as? Markdown.ListItem)?.checkbox
                    let marker=checkbox.map{$0 == .checked ? "☑" : "☐"} ?? first.map{"\($0+UInt(offset))."} ?? "•"
                    return MarkdownBlock(id:offset,kind:"item",text:"",marker:marker,children:convert(item.children))
                }
                return MarkdownBlock(id:index,kind:"list",text:"",children:items)
            }
            if let html=node as? Markdown.HTMLBlock {
                // Raw HTML is selectable evidence, never an executable web view.
                return MarkdownBlock(id:index,kind:"html",text:html.rawHTML)
            }
            return MarkdownBlock(id:index,kind:"paragraph",text:node.children.map{$0.detachedFromParent.format()}.joined())
        }
    }
    return convert(document.children)
}
public func inlineMarkdown(_ text:String)->AttributedString{
    var result=(try? AttributedString(markdown:text,options:.init(interpretedSyntax:.inlineOnlyPreservingWhitespace))) ?? AttributedString(text)
    for run in result.runs{if let url=run.link,!["http","https"].contains(url.scheme ?? ""){result[run.range].link=nil}}
    return result
}

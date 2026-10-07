import SwiftUI
import AppKit
import WixalMarkdown

/// AppKit table keeps real column-header, row and cell accessibility semantics.
struct MarkdownTable:NSViewRepresentable {
    let rows:[[String]]
    let theme:WixalTheme
    let fontSize:CGFloat
    var alignments:[NSTextAlignment]=[]
    private func cellText(_ text:String,column:Int)->NSAttributedString {
        let parsed=inlineMarkdown(text)
        let result=NSMutableAttributedString(string:"")
        let paragraph=NSMutableParagraphStyle()
        paragraph.alignment=column<alignments.count ? alignments[column] : .left
        for run in parsed.runs {
            let intent=run.inlinePresentationIntent ?? []
            var font=intent.contains(.code) ? NSFont.monospacedSystemFont(ofSize:fontSize,weight:.regular) : NSFont.systemFont(ofSize:fontSize)
            var traits:NSFontTraitMask=[]
            if intent.contains(.stronglyEmphasized){traits.insert(.boldFontMask)}
            if intent.contains(.emphasized){traits.insert(.italicFontMask)}
            if !traits.isEmpty{font=NSFontManager.shared.convert(font,toHaveTrait:traits)}
            var attributes:[NSAttributedString.Key:Any]=[.font:font,.foregroundColor:NSColor(theme.text),.paragraphStyle:paragraph]
            if let link=run.link{attributes[.link]=link;attributes[.foregroundColor]=NSColor(theme.accent)}
            result.append(NSAttributedString(string:String(parsed[run.range].characters),attributes:attributes))
        }
        return result
    }
    final class Coordinator:NSObject,NSTableViewDataSource,NSTableViewDelegate {
        var parent:MarkdownTable
        init(_ parent:MarkdownTable){self.parent=parent}
        func numberOfRows(in tableView:NSTableView)->Int{max(0,parent.rows.count-1)}
        func tableView(_ tableView:NSTableView,viewFor tableColumn:NSTableColumn?,row:Int)->NSView?{
            let index=Int(tableColumn?.identifier.rawValue ?? "") ?? 0
            guard row+1<parent.rows.count,index<parent.rows[row+1].count else{return nil}
            let rendered=parent.cellText(parent.rows[row+1][index],column:index)
            let field=NSTextField(wrappingLabelWithString:rendered.string);field.attributedStringValue=rendered;field.isSelectable=true;field.backgroundColor = .clear;field.setAccessibilityLabel(String(inlineMarkdown(parent.rows.first?[index] ?? "Column").characters)+": "+rendered.string);return field
        }
        func tableView(_ tableView:NSTableView,heightOfRow row:Int)->CGFloat{
            guard row+1<parent.rows.count else{return 32}
            let heights=parent.rows[row+1].enumerated().map{index,text->CGFloat in let width=index<tableView.tableColumns.count ? max(50,tableView.tableColumns[index].width-10) : 150;return parent.cellText(text,column:index).boundingRect(with:NSSize(width:width,height:1000),options:[.usesLineFragmentOrigin]).height+14}
            return min(220,max(32,heights.max() ?? 32))
        }
    }
    func makeCoordinator()->Coordinator{Coordinator(self)}
    func makeNSView(context:Context)->NSScrollView{
        let scroll=NSScrollView();scroll.hasHorizontalScroller=true;scroll.hasVerticalScroller=true;scroll.autohidesScrollers=true;scroll.drawsBackground=false;scroll.borderType = .lineBorder
        let table=NSTableView();table.delegate=context.coordinator;table.dataSource=context.coordinator;table.columnAutoresizingStyle = .uniformColumnAutoresizingStyle;table.usesAlternatingRowBackgroundColors=false;table.gridStyleMask=[.solidHorizontalGridLineMask,.solidVerticalGridLineMask];table.intercellSpacing=NSSize(width:10,height:4);table.setAccessibilityLabel("Markdown table");scroll.documentView=table;return scroll
    }
    func updateNSView(_ scroll:NSScrollView,context:Context){
        context.coordinator.parent=self
        guard let table=scroll.documentView as? NSTableView else{return}
        let headings=(rows.first ?? []).map{String(inlineMarkdown($0).characters)}
        if table.tableColumns.count != headings.count{for column in table.tableColumns{table.removeTableColumn(column)};for (index,heading) in headings.enumerated(){let column=NSTableColumn(identifier:NSUserInterfaceItemIdentifier(String(index)));column.title=heading;column.minWidth=110;column.width=max(130,CGFloat(heading.count)*7+24);table.addTableColumn(column)}}
        for (index,column) in table.tableColumns.enumerated(){column.title=headings[index];column.headerCell.font=NSFont.systemFont(ofSize:fontSize,weight:.semibold);column.headerCell.textColor=NSColor(theme.text)}
        table.backgroundColor=NSColor(theme.panel);table.gridColor=NSColor(theme.line);table.reloadData()
    }
}

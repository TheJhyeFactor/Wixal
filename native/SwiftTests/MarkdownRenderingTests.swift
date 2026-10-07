import Foundation
import WixalMarkdown

struct MarkdownRenderingChecks {
    func testNestedMultilineListAndTaskItems() {
        let blocks=markdownBlocks("""
        3. First paragraph

           Continuation paragraph.

           - [x] Finished
           - [ ] Remaining
        4. Next item
        """)
        requireEqual(blocks.count,1)
        requireEqual(blocks[0].kind,"list")
        let items=blocks[0].children
        requireEqual(items.map(\.marker),["3.","4."])
        requireEqual(items[0].children.map(\.kind),["paragraph","paragraph","list"])
        requireEqual(items[0].children[0].text,"First paragraph")
        requireEqual(items[0].children[1].text,"Continuation paragraph.")
        requireEqual(items[0].children[2].children.map(\.marker),["☑","☐"])
        requireEqual(items[0].children[2].children[0].children[0].text,"Finished")
    }

    func testSetextReferenceLinksQuoteAndFence() {
        let blocks=markdownBlocks("""
        Heading
        =======

        Read [documentation][docs].

        > Quoted paragraph
        >
        > ~~~~swift
        > let value = "```"
        > ~~~~

        [docs]: https://docs.python.org/3/
        """)
        requireEqual(blocks.map(\.kind),["heading","paragraph","quote"])
        requireEqual(blocks[0].level,1)
        requireTrue(blocks[1].text.contains("https://docs.python.org/3/"))
        requireEqual(blocks[2].children.map(\.kind),["paragraph","code"])
        requireEqual(blocks[2].children[0].text,"Quoted paragraph")
        requireEqual(blocks[2].children[1].language,"swift")
        requireEqual(blocks[2].children[1].text,"let value = \"```\"\n")
    }

    func testEscapedTablePipesAndInertHTML() {
        let blocks=markdownBlocks("""
        | Name | Value |
        | :--- | ---: |
        | A\\|B | **bold** |

        <script>alert('never execute')</script>
        """)
        requireEqual(blocks.map(\.kind),["table","html"])
        requireEqual(blocks[0].rows.count,2)
        requireEqual(blocks[0].alignments,[.left,.right])
        requireEqual(String(inlineMarkdown(blocks[0].rows[1][0]).characters),"A|B")
        requireEqual(String(inlineMarkdown(blocks[0].rows[1][1]).characters),"bold")
        requireTrue(blocks[1].text.contains("<script>"))
    }

    func testUnsafeInlineLinksHaveNoNavigationDestination() {
        let value=inlineMarkdown("[unsafe](file:///etc/passwd) and [safe](https://docs.python.org/3/)")
        requireEqual(value.runs.compactMap(\.link).map(\.scheme),["https"])
    }
}

private func requireEqual<T:Equatable>(_ actual:T,_ expected:T,file:StaticString=#fileID,line:UInt=#line) {
    guard actual==expected else { fatalError("Expected \(expected), received \(actual)",file:file,line:line) }
}
private func requireTrue(_ value:Bool,file:StaticString=#fileID,line:UInt=#line) {
    guard value else { fatalError("Required parser behavior was absent",file:file,line:line) }
}
@main enum MarkdownAcceptance {
    static func main() {
        let checks=MarkdownRenderingChecks()
        checks.testNestedMultilineListAndTaskItems()
        checks.testSetextReferenceLinksQuoteAndFence()
        checks.testEscapedTablePipesAndInertHTML()
        checks.testUnsafeInlineLinksHaveNoNavigationDestination()
        print("{\"status\":\"passed\",\"checks\":4,\"implementation\":\"production WixalMarkdown parser\"}")
    }
}

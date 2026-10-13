import SwiftUI

/// Wrapping tabs keep section navigation visible in narrow settings panes.
struct QuietSettingsTabs: View {
    let items: [String]
    @Binding var selection: String
    @Environment(\.wixalTheme) private var theme
    var body: some View {
        ViewThatFits(in:.horizontal) {
            HStack(spacing:4) { buttons }
            VStack(alignment:.leading,spacing:4) { buttons }
        }.frame(maxWidth:.infinity,alignment:.leading)
    }
    private var buttons: some View {
        ForEach(items,id:\.self) { item in
            Button { selection=item } label: {
                Text(item).wixalFont(size:12,weight:.medium).padding(.horizontal,12).padding(.vertical,8)
                    .background(selection==item ? theme.selected : .clear,in:RoundedRectangle(cornerRadius:6))
                    .foregroundStyle(selection==item ? theme.accent : theme.muted)
            }.buttonStyle(WixalNavigationButtonStyle(selected:selection==item)).accessibilityAddTraits(selection==item ? .isSelected : [])
        }
    }
}

import SwiftUI
import AppKit

// Original Wixal logo vectors from ui/index.html, drawn natively rather than a raster substitute.
struct LaunchSymbol:Shape {
    var fold=false
    func path(in rect:CGRect)->Path {
        var p=Path()
        func point(_ x:CGFloat,_ y:CGFloat)->CGPoint{CGPoint(x:x*1.16+8,y:y*1.16+32)}
        func move(_ x:CGFloat,_ y:CGFloat){p.move(to:point(x,y))}
        func line(_ x:CGFloat,_ y:CGFloat){p.addLine(to:point(x,y))}
        func curve(_ x:CGFloat,_ y:CGFloat,_ cx:CGFloat,_ cy:CGFloat){p.addQuadCurve(to:point(x,y),control:point(cx,cy))}
        if fold{move(82,66);line(98,19);line(114,19);line(92,87);curve(86,91,91,91);line(79,91);curve(73,87,74,91);line(68,73)}
        else{move(9,19);line(25,19);line(41,66);line(54,31);line(68,31);line(82,66);line(98,19);line(114,19);line(92,87);curve(86,91,91,91);line(79,91);curve(73,87,74,91);line(61,54);line(49,87);curve(42,91,47,91);line(35,91);curve(29,87,31,91)}
        p.closeSubpath();return p.applying(CGAffineTransform(scaleX:rect.width/436,y:rect.height/160))
    }
}
struct LaunchLetters:Shape {
    func path(in rect:CGRect)->Path {
        var p=Path()
        func pt(_ x:CGFloat,_ y:CGFloat)->CGPoint{CGPoint(x:158+x*2.12,y:49+y*2.12)}
        func segment(_ x:CGFloat,_ y:CGFloat,_ xx:CGFloat,_ yy:CGFloat){p.move(to:pt(x,y));p.addLine(to:pt(xx,yy))}
        segment(0,9,0,38);segment(19,9,45,38);segment(45,9,19,38)
        p.addEllipse(in:CGRect(x:158+59*2.12,y:49+9*2.12,width:28*2.12,height:30*2.12))
        segment(87,9,87,38);segment(108,-9,108,31);p.addQuadCurve(to:pt(116,38),control:pt(108,38))
        return p.applying(CGAffineTransform(scaleX:rect.width/436,y:rect.height/160))
    }
}
struct LaunchView:View {
    let theme:WixalTheme
    let motion:Bool
    let sound:Bool
    let done:()->Void
    @ViewState<CGFloat> private var reveal=0
    @ViewState<Bool> private var shown=false
    @ViewState<Bool> private var folded=false
    @ViewState<Bool> private var version=false
    @ViewState<Bool> private var exited=false
    @ViewState<NSSound?> private var chime=nil
    var body:some View {
        VStack(spacing:10){
            ZStack(alignment:.topLeading){
                LaunchSymbol().fill(theme.text)
                LaunchSymbol(fold:true).fill(theme.accent).opacity(folded ? 1 : 0)
                ZStack(alignment:.topLeading){LaunchLetters().stroke(theme.text,style:StrokeStyle(lineWidth:14.84,lineCap:.round,lineJoin:.round));Circle().fill(theme.text).frame(width:16.96,height:16.96).offset(x:149.52,y:25.68)}
                    .offset(x:shown ? 0 : -6).mask(alignment:.topLeading){Rectangle().frame(width:reveal,height:160).offset(x:148)}
            }.frame(width:436,height:160).opacity(shown ? 1 : 0).offset(y:shown ? 0 : 7).scaleEffect(shown ? 1 : 0.985)
            Text("v" + (Bundle.main.object(forInfoDictionaryKey:"CFBundleShortVersionString") as? String ?? "0.7.8")).font(.system(size:12)).foregroundStyle(theme.muted).opacity(version ? 1 : 0).offset(y:version ? 0 : 4)
        }.frame(maxWidth:.infinity,maxHeight:.infinity).background(theme.background).opacity(exited ? 0 : 1).offset(y:exited ? -4 : 0).accessibilityLabel("Wixal is starting")
        .task {
            if sound,let url=Bundle.main.url(forResource:"launch",withExtension:"wav",subdirectory:"audio"),let audio=NSSound(contentsOf:url,byReference:true){chime=audio;audio.volume=0.32;audio.play()}
            guard motion else{done();return}
            withAnimation(.easeOut(duration:0.58)){shown=true}
            try? await Task.sleep(for:.milliseconds(180));guard !Task.isCancelled else{return}
            withAnimation(.timingCurve(0.215,0.61,0.355,1,duration:1.02)){reveal=285}
            try? await Task.sleep(for:.milliseconds(50));guard !Task.isCancelled else{return}
            withAnimation(.easeOut(duration:0.52)){folded=true}
            try? await Task.sleep(for:.milliseconds(530));guard !Task.isCancelled else{return}
            withAnimation(.easeOut(duration:0.42)){version=true}
            try? await Task.sleep(for:.milliseconds(1120));guard !Task.isCancelled else{return}
            withAnimation(.easeIn(duration:0.2)){exited=true}
            try? await Task.sleep(for:.milliseconds(220));guard !Task.isCancelled else{return};done()
        }.onExitCommand{chime?.stop();done()}
        .onDisappear{if exited == false{chime?.stop()}}
    }
}

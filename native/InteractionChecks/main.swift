import Foundation
import WixalInteractions

var checks = 0
func check(_ condition: @autoclosure () -> Bool, _ message: String) {
    guard condition() else { fatalError(message) }
    checks += 1
}
var save = AcknowledgedSubmission()
let first = save.begin()!
check(save.isSubmitting, "Editor must wait for its acknowledgement")
check(save.begin() == nil, "Duplicate save must be blocked")
check(!save.finish(UUID()), "An unrelated acknowledgement must be ignored")
check(save.isSubmitting, "An unrelated reply must not enable another save")
save.finish(first, error: "Engine rejected the draft")
check(!save.isSubmitting && save.error == "Engine rejected the draft", "Rejection must remain visible and permit correction")
let corrected = save.begin()!
check(save.error.isEmpty, "Retry must clear the previous error")
check(!save.finish(first), "A delayed previous reply must not settle the retry")
check(save.isSubmitting, "Retry must continue waiting for its own reply")
save.finish(corrected)
check(!save.isSubmitting && save.error.isEmpty, "Acknowledged correction must succeed")

var guidance = AcknowledgedDraft()
check(guidance.begin() == nil, "Blank guidance cannot be submitted")
guidance.text = "Keep this draft after a failure"
let rejected = guidance.begin()!
guidance.finish(rejected.id, error: "No active run accepts guidance")
check(guidance.text == rejected.text && !guidance.submission.error.isEmpty, "Rejected guidance must retain its text and error")
let accepted = guidance.begin()!
guidance.finish(accepted.id)
check(guidance.text.isEmpty, "Acknowledged unchanged guidance should clear")
guidance.text = "Original guidance"
let edited = guidance.begin()!
guidance.text = "New guidance typed during submission"
guidance.finish(edited.id)
check(guidance.text == "New guidance typed during submission", "A reply must not erase newly typed guidance")
let reverted = guidance.begin()!
guidance.text = "Temporary edit"
guidance.text = reverted.text
guidance.finish(reverted.id)
check(guidance.text == reverted.text, "Editing and reverting still makes the draft newer than its submission")
let latest = guidance.begin()!
guidance.finish(reverted.id)
check(guidance.submission.isSubmitting, "Duplicate old reply must not clear a newer pending draft")
guidance.finish(latest.id)
check(guidance.text.isEmpty, "The current unchanged draft clears on its own acknowledgement")
let runA=RunGuidanceDrafts.key(owner:"guest",run:"run-a")
let runB=RunGuidanceDrafts.key(owner:"guest",run:"run-b")
let accountA=RunGuidanceDrafts.key(owner:"account:other",run:"run-a")
var drafts=RunGuidanceDrafts()
drafts[runA].text="Retained run A draft"
let requestA=drafts[runA].begin()!
drafts[runB].text="Independent run B draft"
drafts[runA].text="Edited while viewing another page"
drafts[runA].finish(requestA.id)
check(drafts[runA].text=="Edited while viewing another page","Reply must preserve edited text across view recreation")
check(drafts[runB].text=="Independent run B draft","A different run must retain its own draft")
check(drafts[accountA].text.isEmpty,"Drafts must be isolated by owner")
let pendingB=drafts[runB].begin()!
check(drafts[runB].submission.isSubmitting,"Reopening a run must retain its pending submission")
let savedTexts=try JSONEncoder().encode(drafts.texts)
let reopened=RunGuidanceDrafts(texts:try JSONDecoder().decode([String:String].self,from:savedTexts))
check(reopened[runA].text==drafts[runA].text && reopened[runB].text==drafts[runB].text,"Relaunch must restore each unsent text")
check(!reopened[runB].submission.isSubmitting,"Relaunch must not automatically resubmit an uncertain request")
drafts[runB].finish(pendingB.id)
check(drafts[runB].text.isEmpty && drafts.texts[runB]==nil,"Acknowledged text must be removed from the persisted snapshot")
check(RunGuidanceDrafts.key(owner:"a",run:"bc") != RunGuidanceDrafts.key(owner:"ab",run:"c"),"Owner and run keys must not collide")
// Persisted navigation preferences must tolerate old/corrupt values and keep
// presentation destinations separate from the two engine session modes.
check(WorkspaceArea.destination("Chat") == .chats,"Legacy Chat route must remain valid")
check(WorkspaceArea.destination("Cybersecurity") == .cybersecurity,"Security is a presentation workspace")
check(WorkspaceArea.destination("Files") == nil,"Project destination must not replace selected workspace")
check(SidebarPreferences.width(.nan)==248,"Invalid saved width must recover")
check(SidebarPreferences.width(100)==216 && SidebarPreferences.width(900)==320,"Saved width must clamp")
check(SidebarPreferences.pins("not-json").isEmpty,"Corrupt pins must recover without deleting sessions")
check(SidebarPreferences.pins("[\"a\",\"a\",\"\",\"b\"]")==["a","b"],"Pin IDs must be unique, ordered and valid")
check(SidebarPreferences.pins(SidebarPreferences.encodePins(["project-session","personal-session"])) == ["project-session","personal-session"],"Pins must round trip without changing identity")
print("{\"status\":\"passed\",\"checks\":\(checks),\"implementation\":\"production WixalInteractions submission and guidance state\"}")

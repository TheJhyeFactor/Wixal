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
print("{\"status\":\"passed\",\"checks\":\(checks),\"implementation\":\"production WixalInteractions submission and guidance state\"}")

"""Bounded run accounting and exact, settled no-progress detection.

Native adaptations of Hermes's budget warnings and bounded conversation loop.
No tool authority is granted here and no action is retried automatically.
"""
import hashlib
import json


class RunControl:
    def __init__(self, max_turns, max_calls):
        self.max_turns = max_turns
        self.max_calls = max_calls
        self.calls = 0
        self.previous = None
        self.repetitions = 0

    def snapshot(self, turn):
        return dict(turnsUsed=turn, turnsLimit=self.max_turns,
                    callsUsed=self.calls, callsLimit=self.max_calls,
                    turnsRemaining=max(0, self.max_turns-turn),
                    callsRemaining=max(0, self.max_calls-self.calls))

    def closing(self, turn):
        # A one-turn profile must still be allowed to perform its requested action.
        return self.calls >= self.max_calls or self.max_turns > 1 and turn == self.max_turns

    def observe(self, checkpoints):
        # Polling a live job is expected to return unchanged data. Errors already
        # have a separate retry limiter; neither belongs in this detector.
        polling = {'network_read', 'command_read', 'addon_job'}
        if not checkpoints or any(c.get('status') != 'finished' or c['name'] in polling
                                  or str(c.get('result', '')).startswith(('User declined', 'Not executed:'))
                                  for c in checkpoints):
            self.previous = None
            self.repetitions = 0
            return False
        settled = [dict(name=c['name'], arguments=c.get('arguments', {}),
                        result=c.get('result', '')) for c in checkpoints]
        fingerprint = hashlib.sha256(json.dumps(settled, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.repetitions = self.repetitions + 1 if fingerprint == self.previous else 1
        self.previous = fingerprint
        return self.repetitions >= 3


def budget_notice(task):
    budget = task.get('runBudget')
    if not budget:
        return ''
    text = ('\nCurrent run limits: '+json.dumps(budget)+'. These count this attempt only; '
            'retained checkpoints from earlier attempts are still evidence.')
    if task.get('stopReason') == 'no_progress':
        return text + (' Three consecutive tool batches returned identical inputs and results. '
                       'Tool execution is stopped. Explain the repeated evidence and unfinished work; '
                       'the controller will pause this run for inspection.')
    if budget.get('closing'):
        return text + (' This is the reserved conclusion turn. No tools are available. '
                       'State what the recorded evidence establishes and what remains unfinished. '
                       'Do not claim that the run limit establishes success.')
    if budget['turnsUsed'] >= .8*budget['turnsLimit'] or budget['callsUsed'] >= .8*budget['callsLimit']:
        text += (' Run limits are nearly exhausted. Prioritize necessary verification and checklist updates. '
                 'Use saved evidence instead of repeating actions, then explain any unfinished work.')
    return text

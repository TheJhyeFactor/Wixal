"""Independent grading of explicit scan claims against known listening ports.

This is a conservative contradiction detector, not a claim of complete natural
language understanding. Mandatory raw/structured evidence checks are separate.
"""
import re

def contradictions(answer,open_ports):
    failures=[]
    if re.search(r'\b(?:no|zero)\s+open\s+(?:tcp\s+)?ports\b',answer,re.I):failures.append('Answer denies the independently observed open ports')
    if re.search(r'\ball\s+(?:(?:selected|tested|scanned|specified|requested|tcp)\s+)*(?:ports\s+)?(?:are\s+|were\s+)?(?:closed|filtered)\b',answer,re.I):failures.append('Answer claims all selected ports are closed or filtered')
    for sentence in re.split(r'[\n.!?]',answer):
        if not re.search(r'\b(?:closed|filtered)\b',sentence,re.I):continue
        if re.search(r'\b(?:not|neither|outside|other|unscanned)\b',sentence,re.I):continue
        for port in open_ports:
            if re.search(r'(?<!\d)'+str(port)+r'(?!\d)',sentence):failures.append(f'Answer assigns closed/filtered status to observed open port {port}')
    return failures

def claims_inspection(answer):
    for sentence in re.split(r'[\n.!?]',answer):
        if re.search(r"\b(?:not|never|unable|cannot|can't|declined|failed|unavailable|only)\b",sentence,re.I):continue
        if re.search(r'\b(?:I|we)\s+(?:have\s+)?inspected\b|\b(?:ports|services)\s+(?:were|are|have been)\s+inspected\b',sentence,re.I):return True
        if re.search(r'\binspection\b',sentence,re.I) and re.search(r'\b(?:completed?|finished|successful(?:ly)?|done)\b',sentence,re.I):return True
    return False

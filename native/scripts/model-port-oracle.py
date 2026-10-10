"""Independent grading of explicit scan claims against known listening ports.

This is a conservative contradiction detector, not a claim of complete natural
language understanding. Mandatory raw/structured evidence checks are separate.
"""
import re

def contradictions(answer,open_ports):
    answer=re.sub(r'\bno\s+open\s+ports(?:\s+detected)?\s+does\s+not\s+establish[^.!?\n]*','',answer,flags=re.I)
    failures=[]
    if re.search(r'\b(?:no|zero)\s+open\s+(?:tcp\s+)?ports\b',answer,re.I):failures.append('Answer denies the independently observed open ports')
    if re.search(r'\ball\s+(?:(?:selected|tested|scanned|specified|requested|tcp)\s+)*(?:ports\s+)?(?:are\s+|were\s+)?(?:closed|filtered)\b',answer,re.I):failures.append('Answer claims all selected ports are closed or filtered')
    for sentence in re.split(r'[\n.!?]',answer):
        denies_open=bool(re.search(r'\bneither\b.*\bopen\b|\bnot\s+open\b',sentence,re.I))
        if denies_open and not re.search(r"\b(?:cannot|can't|outside|other|unscanned)\b",sentence,re.I) and any(re.search(r'(?<!\d)'+str(port)+r'(?!\d)',sentence) for port in open_ports):failures.append('Answer denies an independently observed open port')
        if not re.search(r'\b(?:closed|filtered)\b',sentence,re.I):continue
        if re.search(r'\b(?:not|neither|outside|other|unscanned)\b',sentence,re.I):continue
        for port in open_ports:
            if re.search(r'(?<!\d)'+str(port)+r'(?!\d)',sentence):failures.append(f'Answer assigns closed/filtered status to observed open port {port}')
    return failures

def claims_inspection(answer):
    for sentence in re.split(r'[\n.!?]',answer):
        if re.search(r"\b(?:not|never|unable|cannot|can't|declined|failed|unavailable|pending|planned|hypothetical|earlier|previous)\b",sentence,re.I):continue
        if re.search(r'\b(?:I|we)\s+(?:have\s+)?inspected\b|\b(?:ports|services)\s+(?:were|are|have been)\s+inspected\b',sentence,re.I):return True
        if re.search(r'\binspection(?:\s+step)?\s+(?:(?:was|is|has been|had been)\s+)?(?:performed|conducted|carried out)\b|\bused\s+for\s+inspection\b',sentence,re.I):return True
        if re.search(r'\binspection\b',sentence,re.I) and re.search(r'\b(?:completed?|finished|successful(?:ly)?|done)\b',sentence,re.I):return True
        if re.search(r'\binspection\s+(?:confirms?|confirmed|showed|found|identified)\b',sentence,re.I):return True
        if re.search(r'\bsatisfies\s+(?:the\s+)?inspection\s+requirement\b|\bdiscovery\s+output\s+itself\s+is\s+the\s+inspection\s+evidence\b',sentence,re.I):return True
    return False

def quoted_xml_errors(answer,outputs):
    """Grade purported raw XML excerpts against retained scanner bytes."""
    actual=[re.sub(r'\s+',' ',value.strip()) for value in outputs if isinstance(value,str) and value.strip()]
    errors=[]
    for match in re.finditer(r'```xml\s*\n?(.*?)```',answer,re.I|re.S):
        context=answer[max(0,match.start()-240):match.start()]
        if re.search(r'\b(?:example|illustrative|schematic|simplified)\b',context,re.I):continue
        if not re.search(r'\b(?:output|excerpt|verbatim|verified)\b',context,re.I):continue
        quote=re.sub(r'\s+',' ',match.group(1).strip())
        if quote and not any(quote in raw for raw in actual):errors.append('Purported scanner XML excerpt differs from retained actual output')
    return errors

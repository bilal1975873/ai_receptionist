import re
from typing import Optional, List, Dict, Any, Tuple
from rapidfuzz import fuzz

def extract_visitor_info(text: str, field_type: str) -> Optional[str]:
    text = text.strip()
    patterns = {
        "name": r"(?:name|i am|my name is|this is)\s+([A-Za-z\s]+)",
        "cnic": r"(?:cnic|id|identity|number)\s*(?:is|:)?\s*(\d{5}-\d{7}-\d{1})",
        "phone": r"(?:phone|mobile|contact|number)\s*(?:is|:)?\s*(\d{11})",
        "company": r"(?:company|organization|firm|from)\s*(?:is|:)?\s*([A-Za-z\s]+)",
        "host": r"(?:meet|see|visit|with)\s+([A-Za-z\s]+)",
        "purpose": r"(?:purpose|reason|for|to)\s+(?:is|:)?\s*([^.]+)",
    }
    pattern = patterns.get(field_type)
    if not pattern:
        return None
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def find_employee_matches(name: str, employees: List[Dict]) -> Tuple[Optional[Dict], List[Dict]]:
    if not name:
        return None, []
    clean_name = name.lower().strip()
    exact_match = next((emp for emp in employees if clean_name == emp["name"].lower()), None)
    if exact_match:
        return exact_match, []
    name_matches = []
    for emp in employees:
        name_parts = emp["name"].lower().split()
        if any(part == clean_name for part in name_parts):
            name_matches.append(emp)
    if name_matches:
        return None, name_matches
    fuzzy_matches = []
    best_ratio = 0
    for emp in employees:
        full_name_ratio = fuzz.ratio(clean_name, emp["name"].lower())
        name_parts = emp["name"].lower().split()
        part_ratios = [fuzz.ratio(clean_name, part) for part in name_parts]
        best_part_ratio = max(part_ratios) if part_ratios else 0
        token_ratio = fuzz.token_sort_ratio(clean_name, emp["name"].lower())
        partial_ratio = fuzz.partial_ratio(clean_name, emp["name"].lower())
        token_set_ratio = fuzz.token_set_ratio(clean_name, emp["name"].lower())
        ratio = max(full_name_ratio, best_part_ratio, token_ratio, partial_ratio, token_set_ratio)
        best_ratio = max(best_ratio, ratio)
        if ratio >= 60:
            fuzzy_matches.append((emp, ratio))
    fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
    if fuzzy_matches:
        top_ratio = fuzzy_matches[0][1]
        top_matches = [match[0] for match in fuzzy_matches if match[1] >= top_ratio - 20]
        if top_ratio >= 75 and len(top_matches) > 0:
            return None, top_matches[:3]
        return None, [match[0] for match in fuzzy_matches]
    return None, []

def process_selection(input_text: str, options: List[Any]) -> Optional[Any]:
    input_text = input_text.strip().lower()
    if input_text.isdigit() and 1 <= int(input_text) <= len(options):
        return options[int(input_text) - 1]
    for option in options:
        if isinstance(option, dict) and "name" in option:
            if option["name"].lower() == input_text:
                return option
        elif isinstance(option, str):
            if option.lower() == input_text:
                return option
    return None 
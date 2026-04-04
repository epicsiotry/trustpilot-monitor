"""Categorise negative Anima reviews into 7 categories.

Uses keyword/pattern matching that mirrors the manual categorisation methodology
from Joseph's analysis. For production use, this should be replaced with LLM
categorisation via the Claude API for higher accuracy.

Categories:
1. Interface and technical problems
2. Questionnaire burden
3. System unavailability
4. Digital exclusion
5. Triage misdirection
6. Other
7. Practice capacity
"""

import sqlite3
import re
from datetime import datetime, timezone
from database import get_connection

# Category definitions with weighted keyword patterns
# Each tuple is (pattern, weight) - higher weight = stronger signal
CATEGORIES = {
    "Interface and technical problems": [
        (r"crash(ed|es|ing)?", 3),
        (r"bug(s|gy)?", 3),
        (r"login\s*(fail|error|issue|problem)", 4),
        (r"log\s*in\s*(fail|error|issue|problem)", 4),
        (r"can'?t\s*log\s*in", 4),
        (r"unable\s*to\s*log\s*in", 4),
        (r"no\s*back\s*button", 4),
        (r"no\s*way\s*back", 4),
        (r"can'?t\s*go\s*back", 3),
        (r"data\s*loss", 4),
        (r"lost\s*(my|all|everything)", 3),
        (r"timed?\s*out", 3),
        (r"time(d|s)?\s*(me)?\s*out", 3),
        (r"session\s*expir", 3),
        (r"confusing\s*(navigation|interface|layout)", 3),
        (r"poor\s*(user\s*)?interface", 4),
        (r"user\s*interface", 2),
        (r"difficult\s*to\s*navigate", 3),
        (r"hard\s*to\s*navigate", 3),
        (r"navigate", 1),
        (r"settings?\s*(not\s*)?saved", 3),
        (r"cumbersome", 2),
        (r"error\s*message", 3),
        (r"doesn'?t\s*work", 2),
        (r"not\s*work(ing)?", 2),
        (r"broken", 2),
        (r"glitch", 3),
        (r"buffer(s|ing)", 2),
        (r"poorly\s*(designed|written)", 3),
        (r"bad(ly)?\s*designed", 3),
        (r"terrible\s*(design|system|website|app)", 2),
        (r"awful\s*(system|website|app|design)", 2),
        (r"not\s*fit\s*for\s*purpose", 2),
        (r"multiple\s*restart", 3),
        (r"start\s*again", 2),
        (r"false\s*(treatment\s*)?records?", 4),
        (r"incorrect\s*provider", 4),
        (r"sign\s*up\s*again", 3),
        (r"clunky", 2),
        (r"un-?user\s*friendly", 3),
        (r"not\s*user\s*friendly", 3),
        (r"slider", 2),
        (r"text\s*verification.*error", 3),
        (r"verification.*error", 2),
        (r"validate.*fail", 3),
        (r"unable\s*to\s*validate", 4),
        (r"input\s*field.*tiny", 3),
        (r"character\s*limit", 3),
        (r"300\s*character", 3),
        (r"submit\s*button", 2),
        (r"repetitive\s*form", 3),
    ],
    "Questionnaire burden": [
        (r"too\s*(many|long|much)\s*(question|drop\s*down|form|info)", 4),
        (r"(form|questionnaire)\s*(is\s*)?(too\s*)?(long|complex|lengthy)", 4),
        (r"irrelevant\s*(question|info|answer|drop)", 4),
        (r"irrelevant", 2),
        (r"(took|takes?|spend|spent)\s*\d+\s*min", 3),
        (r"takes?\s*(so\s*)?(much\s*)?long(er)?", 2),
        (r"39\s*question", 5),
        (r"lengthy\s*(form|process|question|convoluted)", 3),
        (r"convoluted\s*form", 4),
        (r"complex\s*form", 4),
        (r"stressful\s*(form|process|to\s*fill)", 3),
        (r"fill(ing)?\s*(in|out)\s*(the\s*)?(form|info|questionnaire)", 2),
        (r"repetiti(ve|on)", 2),
        (r"already\s*(have|held|know|on\s*record)", 3),
        (r"asks?\s*(for\s*)?(date\s*of\s*birth|age|sex)", 3),
        (r"asks?\s*(too\s*many|a\s*lot\s*of)?\s*questions?", 2),
        (r"multiple\s*choice.*relevant", 3),
        (r"drop\s*down", 3),
        (r"(yes|no)\s*answer.*simple", 3),
        (r"timer", 2),
        (r"time\s*limit", 3),
        (r"time\s*pressure", 3),
        (r"long\s*time\s*to\s*complete", 3),
        (r"takes?\s*forever", 2),
        (r"(character|char)\s*(limit|allowed)", 3),
        (r"not\s*enough\s*character", 4),
        (r"waded?\s*through", 2),
    ],
    "System unavailability": [
        (r"closed?\s*(by|at|within)\s*\d", 5),
        (r"(8|9|10)\s*:?\s*\d{0,2}\s*(am)?\s*(already\s*)?(closed|full|shut)", 5),
        (r"full\s*(capacity|by)", 4),
        (r"exceeded\s*(the\s*)?(maximum|max)", 5),
        (r"maximum\s*(number\s*of\s*)?requests?\s*(exceeded|reached)", 5),
        (r"not\s*available\s*until", 4),
        (r"unavailable", 3),
        (r"(system|site|app)\s*(wasn'?t|not)\s*available", 4),
        (r"opens?\s*at\s*8\s*am", 3),
        (r"closed\s*(at|by|down|within|after)", 3),
        (r"shut\s*(down|the\s*system)", 4),
        (r"no\s*appointments?", 2),
        (r"can'?t\s*get\s*(an\s*)?appointment", 2),
        (r"never\s*(been\s*)?able\s*to\s*(get|book)", 3),
        (r"can\s*never\s*(get|book)", 3),
        (r"8\s*(am|oclock|o'?clock)\s*(scramble|rush|race|fight)?", 3),
        (r"bun\s*fight", 3),
        (r"cap\s*(on|the)\s*(number|enquir)", 4),
        (r"reach(ed)?\s*(full\s*)?capacity", 4),
        (r"not\s*24\s*hours?", 3),
        (r"(only|just)\s*(work|open|available|live)\s*(for|until|till)", 3),
        (r"daily\s*quota", 4),
        (r"try\s*(again\s*)?(tomorrow|next\s*day|24\s*hours)", 3),
        (r"impossible\s*to\s*(get|book)", 2),
        (r"we\s*are\s*full", 4),
        (r"out\s*of\s*hours", 2),
        (r"(not|isn'?t)\s*available\s*(outside|out\s*of|on\s*(the\s*)?weekend)", 4),
        (r"limit(s|ed)?\s*messages?", 3),
        (r"not\s*available\s*on.*weekend", 4),
    ],
    "Digital exclusion": [
        (r"elder(ly)?", 4),
        (r"old(er)?\s*(people|person|patient|folk|customer)", 4),
        (r"over\s*(7[05]|8[025])", 4),
        (r"(age|aged?)\s*(7[05]|8[025])", 3),
        (r"disabled?\b", 4),
        (r"disabilit(y|ies)", 4),
        (r"learning\s*(difficult|disab|need)", 5),
        (r"sight\s*loss", 4),
        (r"vulnerab(le|ility)", 3),
        (r"(can'?t|don'?t|not)\s*(use|access)\s*(the\s*)?(computer|internet|online|digital|phone|app|site)", 3),
        (r"no\s*(computer|internet|phone|access)", 3),
        (r"force(d|s|ing)?\s*(to\s*)?(go\s*)?online", 3),
        (r"push(ing|ed)?\s*(all|everyone|patient)?\s*online", 3),
        (r"digital(ly)?\s*(exclu|confiden|literat)", 4),
        (r"bipolar", 3),
        (r"can'?t\s*access\s*(it|this|the)", 2),
        (r"(how|what)\s*(do|would|can)\s*(older|elderly)", 4),
        (r"my\s*(mum|dad|mother|father|gran|wife|husband).*confus", 3),
        (r"(mum|dad|mother|father|gran).*can'?t", 3),
        (r"set\s*(it\s*)?up\s*for\s*(me|him|her)", 2),
        (r"son\s*(downloaded|set\s*up|helped)", 3),
    ],
    "Triage misdirection": [
        (r"(told|says?|said|telling|redirect|refer|sent|direct|end)\s*(me\s*)?(to\s*)?(call\s*)?(999|a\s*(&|and)\s*e|a&e|hospital|111|emergency)", 5),
        (r"(go\s*to|attend|visit)\s*(a\s*(&|and)\s*e|a&e|hospital|emergency)", 3),
        (r"(recommend|suggest|direct)\s*(ed|s)?\s*(me\s*)?(to\s*)?(999|a\s*(&|and)\s*e|a&e|hospital|111)", 5),
        (r"(call|phone|ring|dial)\s*(999|111)", 5),
        (r"999", 3),
        (r"111", 2),
        (r"a\s*(&|and)\s*e|a&e", 3),
        (r"signpost(ing)?\s*(inappropriately)?", 3),
        (r"(wrong|incorrect)\s*(place|appointment|diagnosis|type)", 4),
        (r"phone\s*appointment.*face\s*to\s*face", 3),
        (r"face\s*to\s*face.*phone\s*appointment", 3),
        (r"(book|want)(ed)?\s*face\s*to\s*face.*(got|gave|given|booked)\s*(me\s*)?.*phone", 4),
        (r"misidentif", 4),
        (r"misguided", 3),
        (r"tummy\s*problem.*hip", 5),
        (r"hip.*tummy\s*problem", 5),
        (r"inappropriate(ly)?", 2),
        (r"not\s*an?\s*emergency", 3),
        (r"sick\s*child.*blood\s*test.*cancer", 5),
        (r"bladder.*(sick\s*child|blood\s*test|cancer)", 5),
        (r"fobbed\s*off", 2),
    ],
    "Practice capacity": [
        (r"(surgery|practice|gp)\s*(is\s*)?(full|no\s*space|no\s*room)", 4),
        (r"(wait|waiting)\s*(list|time)?\s*(\d+\s*)?(week|month|day)", 3),
        (r"(two|2|three|3|four|4)\s*months?\s*(wait|later)", 4),
        (r"no\s*(available\s*)?appointment.*weeks?", 3),
        (r"booked\s*(up|solid|out)", 3),
        (r"(staff|receptionist|reception)\s*(are\s*)?(rude|unhelpful|couldn'?t)", 2),
        (r"(prescription|prescriptions?)\s*(delay|late|slow|taking\s*too\s*long)", 4),
        (r"referral.*not.*completed", 3),
        (r"(no\s*)?response.*(\d+\s*)?(day|week)", 2),
    ],
}


def categorise_review(title, text):
    """Categorise a single review. Returns (category, software_complaint, confidence)."""
    full_text = f"{title} {text}".lower()

    scores = {}
    for category, patterns in CATEGORIES.items():
        score = 0
        matches = 0
        for pattern, weight in patterns:
            found = re.findall(pattern, full_text, re.IGNORECASE)
            if found:
                score += weight * len(found)
                matches += 1
        scores[category] = (score, matches)

    # Find the best category
    best_category = max(scores, key=lambda k: (scores[k][0], scores[k][1]))
    best_score = scores[best_category][0]

    # If no patterns matched at all, label as "Other"
    if best_score == 0:
        best_category = "Other"
        confidence = 0.3
    else:
        # Calculate confidence based on score magnitude and margin over second-best
        sorted_scores = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        margin = sorted_scores[0][0] - sorted_scores[1][0] if len(sorted_scores) > 1 else sorted_scores[0][0]
        confidence = min(0.95, 0.4 + (margin / max(best_score, 1)) * 0.4 + min(best_score / 15, 0.15))

    # Determine if this is a software complaint or practice complaint
    software_complaint = True
    if best_category == "Practice capacity":
        software_complaint = False
    elif best_category == "Other":
        # Check if it's about the practice rather than software
        practice_signals = len(re.findall(
            r"(receptionist|reception|staff|doctor|gp|surgery)\s*(was|were|is|are)\s*(rude|unhelpful|useless)",
            full_text, re.IGNORECASE
        ))
        software_signals = len(re.findall(
            r"(app|system|site|website|platform|interface|anima)",
            full_text, re.IGNORECASE
        ))
        if practice_signals > software_signals:
            software_complaint = False

    return best_category, software_complaint, round(confidence, 2)


def categorise_all():
    """Categorise all uncategorised 1-2 star Anima reviews."""
    conn = get_connection()

    # Get uncategorised negative reviews
    rows = conn.execute("""
        SELECT id, title, text FROM reviews
        WHERE company = 'anima' AND rating <= 2 AND category IS NULL
    """).fetchall()

    print(f"Found {len(rows)} uncategorised negative reviews")

    now = datetime.now(timezone.utc).isoformat()
    counts = {}

    for row in rows:
        category, software_complaint, confidence = categorise_review(
            row["title"] or "", row["text"] or ""
        )
        conn.execute("""
            UPDATE reviews SET
                category = ?,
                software_complaint = ?,
                category_confidence = ?,
                categorised_at = ?
            WHERE id = ?
        """, (category, 1 if software_complaint else 0, confidence, now, row["id"]))

        counts[category] = counts.get(category, 0) + 1

    conn.commit()

    print("\nCategorisation results:")
    total = sum(counts.values())
    for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total > 0 else 0
        print(f"  {cat}: {count} ({pct:.1f}%)")

    software = conn.execute("""
        SELECT COUNT(*) FROM reviews
        WHERE company = 'anima' AND rating <= 2 AND software_complaint = 1
    """).fetchone()[0]
    practice = conn.execute("""
        SELECT COUNT(*) FROM reviews
        WHERE company = 'anima' AND rating <= 2 AND software_complaint = 0
    """).fetchone()[0]
    print(f"\nSoftware complaints: {software}")
    print(f"Practice complaints: {practice}")

    conn.close()


if __name__ == "__main__":
    categorise_all()

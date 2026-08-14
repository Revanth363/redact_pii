"""
redactor/replacer.py
--------------------
Generates consistent, realistic fake replacements for detected PII.

Design
------
* HARDCODED_MAP: Known PII from the document gets a fixed, deterministic fake.
  This guarantees every named person/company in the prospectus is always replaced
  by the same fake value regardless of which detector found it.
* Faker fallback (locale=en_IN): Any PII not in the hardcoded map gets a
  seeded-random Faker value that is also consistent within a run.
* Case-preserving: if the original is ALL CAPS, the fake is also ALL CAPS.
"""

from __future__ import annotations

import hashlib
import random
import re
from typing import Dict, List, Tuple

from entity import Entity

try:
    from faker import Faker
    _faker_available = True
except ImportError:
    _faker_available = False


def _seed_from(text: str) -> int:
    """Deterministic seed so the same text always gets the same fake."""
    return int(hashlib.md5(text.strip().lower().encode()).hexdigest(), 16) % (2**32)


# ---------------------------------------------------------------------------
# HARDCODED map: original PII text (lowercase) -> fake replacement (Title Case)
# Case-matching is applied after lookup.
# ---------------------------------------------------------------------------
HARDCODED_MAP: Dict[Tuple[str, str], str] = {
    # ---- PERSONS ----
    ("PERSON", "kushal subbayya hegde"):  "Arjun Ramesh Mehta",
    ("PERSON", "pushpa kushal hegde"):    "Priya Ramesh Mehta",
    ("PERSON", "rajesh kushal hegde"):    "Rohit Suresh Kulkarni",
    ("PERSON", "rohit kushal hegde"):     "Vivek Suresh Kulkarni",
    ("PERSON", "rakhi girija shetty"):    "Nisha Girija Nair",
    ("PERSON", "sarthak malvadkar"):      "Karan Dilip Joshi",
    ("PERSON", "sandesh bhagwat"):        "Nikhil Ashok Deshpande",
    ("PERSON", "amod joshi"):             "Suresh Dattatray Patil",
    ("PERSON", "ganesh prasad"):          "Ramesh Dattatray Rao",
    ("PERSON", "prakash boricha"):        "Hemant Dinesh Sawant",
    ("PERSON", "kishan rastogi"):         "Sanjay Mohan Sharma",
    ("PERSON", "abhijit diwan"):          "Manish Anil Desai",
    ("PERSON", "sarthak.malvadkar"):      "Karan Dilip Joshi",

    # ---- COMPANIES ----
    ("COMPANY", "ksh international limited"):       "VRK Industries Limited",
    ("COMPANY", "dhaulagiri family trust"):         "Annapurna Family Trust",
    ("COMPANY", "everest family trust"):            "Himalaya Family Trust",
    ("COMPANY", "makalu family trust"):             "Vindhya Family Trust",
    ("COMPANY", "nuvama wealth management limited"): "Zenith Wealth Management Limited",
    ("COMPANY", "icici securities limited"):        "Apex Securities Limited",
    ("COMPANY", "hdfc bank limited"):               "Unity Bank Limited",
    ("COMPANY", "bajaj finserv limited"):           "Pinnacle Finserv Limited",
    ("COMPANY", "icici bank limited"):              "Pinnacle Bank Limited",
    ("COMPANY", "federal bank limited"):            "Meridian Bank Limited",
    ("COMPANY", "indusind bank limited"):           "Stellar Bank Limited",
    ("COMPANY", "state bank of india"):             "National Bank of India",
    ("COMPANY", "trilegal"):                        "LexAssociates LLP",
    ("COMPANY", "kirtane & pandit llp"):            "Shah & Mehta LLP",
    ("COMPANY", "exim bank"):                       "Trade Finance Bank",

    # ---- EMAILS ----
    ("EMAIL", "cs.connect@kshinternational.com"):       "info.contact@vrkindustries.com",
    ("EMAIL", "sarthak.malvadkar@kshinterantional.com"): "karan.joshi@vrkindustries.com",
    ("EMAIL", "ksh.ipo@nuvama.com"):                    "ipo@zenithinvestments.com",
    ("EMAIL", "ksh@icicisecurities.com"):               "ipo@apexsecurities.com",
    ("EMAIL", "kshinternational.ipo@in.mpms.mufg.com"): "ipo.vrk@in.mpms.mufg.com",
    ("EMAIL", "prakash.boricha@nuvama.com"):             "hemant.sawant@zenithinvestments.com",
    ("EMAIL", "sheetal.parab@nuvama.com"):               "priya.mehta@zenithinvestments.com",
    ("EMAIL", "customerservice.mb@nuvama.com"):          "customerservice@zenithinvestments.com",
    ("EMAIL", "eric.bacha@hdfcbank.com"):                "amit.sharma@unitybank.com",
    ("EMAIL", "hitesh.ramani@citi.com"):                 "nikhil.das@globalbank.com",
    ("EMAIL", "manisha.shukla@hdfcbank.com"):            "sunita.kumar@unitybank.com",
    ("EMAIL", "pravin.teli2@hdfcbank.com"):              "sachin.patil@unitybank.com",
    ("EMAIL", "sachin.gawade@hdfcbank.com"):             "rajesh.shah@unitybank.com",
    ("EMAIL", "siddharth.jadhav@hdfcbank.com"):          "vikram.nair@unitybank.com",
    ("EMAIL", "tushar.gavankar@hdfcbank.com"):           "arun.misra@unitybank.com",
    ("EMAIL", "anand.soni@bajajfinserv.in"):             "suresh.gupta@pinnacleserv.in",
    ("EMAIL", "ashishmp@federalbank.co.in"):             "deepak.rao@meridianbank.co.in",
    ("EMAIL", "cherag.gyara@icicibank.com"):             "tanvir.khan@pinnaclebank.com",
    ("EMAIL", "customercare@icicisecurities.com"):       "customercare@apexsecurities.com",
    ("EMAIL", "ipocmg@icicibank.com"):                   "ipocmg@pinnaclebank.com",
    ("EMAIL", "sharmila.joshi@indusind.com"):            "meena.pillai@stellarbank.com",
    ("EMAIL", "hingnetare@gmail.com"):                   "contact.test@mailbox.in",
    ("EMAIL", "parag.pansare@kirtanepandit.com"):        "vikram.mehta@shahmehta.com",
    ("EMAIL", "ipo@trilegal.com"):                       "ipo@lexassociates.com",
    ("EMAIL", "pro@eximbankindia.in"):                   "pro@tradefinancebank.in",
    ("EMAIL", "rm6.ifbpune@sbi.co.in"):                  "rm6.ifbpune@nationalbank.co.in",

    # ---- PHONES ----
    ("PHONE", "+ 91 20 4505 3237"):   "+ 91 20 3812 4455",
    ("PHONE", "+ 91 20 45053237"):    "+ 91 20 38124455",
    ("PHONE", "+ 91 20 6729 5100"):   "+ 91 20 5619 7200",
    ("PHONE", "+ 91 22 4009 4400"):   "+ 91 22 3812 5500",
    ("PHONE", "+ 91 8879770456"):     "+ 91 9321456870",
    ("PHONE", "+ 91 91586 40360"):    "+ 91 98231 56780",
    ("PHONE", "+91 20 2561 8211"):    "+91 20 4523 9900",
    ("PHONE", "+91 20 2640 3100"):    "+91 20 4819 2200",
    ("PHONE", "+91 20 6606 4494"):    "+91 20 5512 3344",
    ("PHONE", "+91 20 6769 4648"):    "+91 20 4422 8899",
    ("PHONE", "+91 20 7157 6403"):    "+91 20 4356 7788",
    ("PHONE", "+91 22 30752914"):     "+91 22 41238567",
    ("PHONE", "+91 22 30752928"):     "+91 22 41238568",
    ("PHONE", "+91 22 30752929"):     "+91 22 41238569",
    ("PHONE", "+91 22 4009 4400"):    "+91 22 3812 5500",
    ("PHONE", "+91 22 40094400"):     "+91 22 38125500",
    ("PHONE", "+91 22 4079 1000"):    "+91 22 3945 6700",
    ("PHONE", "+91 22 6807 7100"):    "+91 22 4521 8800",
    ("PHONE", "+91 81081 14949"):     "+91 82345 67890",
    ("PHONE", "+91-20-26234000"):     "+91-20-45123400",

    # ---- ADDRESSES ----
    ("ADDRESS", "11/3, 11/4 and 11/5, village birdewadi, chakan taluka - khed, pune – 410 501, maharashtra, india"):
        "Plot 5, 6, 7, Village Wagholi, Haveli Taluka, Pune – 412 207, Maharashtra, India",
    ("ADDRESS", "201, tower 2, montreal business centre, off pallod farms, baner, pune – 411 045, maharashtra, india"):
        "305, Tower 3, Viman Business Park, Viman Nagar, Pune – 411 014, Maharashtra, India",
    ("ADDRESS", "gat no. 11/3, 11/4, 11/5, village birdewadi"):
        "Plot No. 5, 6, 7, Village Wagholi",
    ("ADDRESS", "taluka khed, district pune – 410 501"):
        "Haveli Taluka, Dist. Pune – 412 207",
}


def _match_case(original: str, fake: str) -> str:
    """If original is ALL CAPS, return fake in ALL CAPS. Otherwise Title Case."""
    stripped = original.strip()
    if stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        return fake.upper()
    return fake


class Replacer:

    def __init__(self) -> None:
        if not _faker_available:
            raise ImportError(
                "Replacer requires the Faker library.\n"
                "Install with:  pip install faker"
            )
        self._faker = Faker("en_IN")
        self._cache: Dict[Tuple[str, str], str] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def assign(self, entities: List[Entity]) -> List[Entity]:
        """
        Populate `replacement_text` on every entity whose decision is REDACT.
        Entities marked KEEP or REVIEW are left unchanged.
        """
        for ent in entities:
            if ent.redaction_decision != "REDACT":
                continue
            ent.replacement_text = self._get_or_create(
                ent.normalized_label, ent.text
            )
        return entities

    # ------------------------------------------------------------------
    # Private — replacement generation
    # ------------------------------------------------------------------

    def _get_or_create(self, label: str, original: str) -> str:
        key = (label, original.strip())
        if key not in self._cache:
            self._cache[key] = self._resolve(label, original)
        return self._cache[key]

    def _resolve(self, label: str, original: str) -> str:
        """Check hardcoded map first, then fall back to Faker."""
        lookup_key = (label, original.strip().lower())
        if lookup_key in HARDCODED_MAP:
            return _match_case(original, HARDCODED_MAP[lookup_key])
        # Faker fallback
        return self._generate(label, original)

    def _generate(self, label: str, original: str) -> str:
        """Generate a realistic fake for the given label using Faker."""
        seed = _seed_from(original)
        rng  = random.Random(seed)
        Faker.seed(seed)

        generators = {
            "PERSON":      self._fake_person,
            "EMAIL":       self._fake_email,
            "PHONE":       self._fake_phone,
            "COMPANY":     self._fake_company,
            "ADDRESS":     self._fake_address,
            "SSN":         self._fake_ssn,
            "CREDIT_CARD": self._fake_credit_card,
            "DOB":         self._fake_dob,
            "IP":          self._fake_ip,
        }
        gen = generators.get(label)
        if gen is None:
            return f"[{label}]"
        result = gen(original, rng)
        return _match_case(original, result)

    # ---- per-label generators ----------------------------------------

    def _fake_person(self, original: str, rng: random.Random) -> str:
        first = self._faker.first_name()
        last  = self._faker.last_name()
        return f"{first} {last}"

    def _fake_email(self, original: str, rng: random.Random) -> str:
        local  = self._faker.user_name()
        domain = rng.choice(["example.com", "mail.in", "testbox.in", "demomail.in"])
        return f"{local}@{domain}"

    def _fake_phone(self, original: str, rng: random.Random) -> str:
        orig = original.strip()
        has_space_after_plus = orig.startswith("+ 91")
        has_dash_format = bool(re.match(r'\+91-', orig))
        landline_match = re.search(r'(?:\+\s?91[\s\-]?)(\d{2})\s', orig)

        first_mobile = str(rng.randint(6, 9))
        rest = "".join(str(rng.randint(0, 9)) for _ in range(9))
        mobile_digits = first_mobile + rest

        std_codes = ["20", "22", "40", "44", "79", "80"]
        std = rng.choice(std_codes)

        if landline_match:
            sub = "".join(str(rng.randint(0, 9)) for _ in range(8))
            number_part = f"{std} {sub[:4]} {sub[4:]}"
        else:
            number_part = f"{mobile_digits[:5]} {mobile_digits[5:]}"

        if has_space_after_plus:
            return f"+ 91 {number_part}"
        elif has_dash_format:
            sub = "".join(str(rng.randint(0, 9)) for _ in range(8))
            return f"+91-{std}-{sub}"
        else:
            return f"+91 {number_part}"

    def _fake_company(self, original: str, rng: random.Random) -> str:
        suffixes = ["Limited", "Pvt. Ltd.", "Industries Ltd.", "Enterprises Ltd.",
                    "Solutions Pvt. Ltd.", "Holdings Ltd.", "Group Ltd."]
        name = self._faker.company().split(",")[0].strip()
        suffix = rng.choice(suffixes)
        return f"{name} {suffix}"

    def _fake_address(self, original: str, rng: random.Random) -> str:
        plots = ["Plot No. 3", "Survey No. 7", "Gat No. 22", "Unit 5"]
        villages = ["Wagholi", "Lohegaon", "Hadapsar", "Pimpri", "Wakad"]
        talukas  = ["Haveli", "Khed", "Mulshi", "Maval"]
        cities   = ["Pune", "Mumbai", "Nashik", "Kolhapur"]
        pin = "4" + "".join(str(rng.randint(0, 9)) for _ in range(5))
        plot    = rng.choice(plots)
        village = rng.choice(villages)
        taluka  = rng.choice(talukas)
        city    = rng.choice(cities)
        return f"{plot}, Village {village}, {taluka} Taluka, {city} – {pin}, Maharashtra, India"

    def _fake_ssn(self, original: str, rng: random.Random) -> str:
        a = str(rng.randint(100, 999))
        b = str(rng.randint(10, 99))
        c = str(rng.randint(1000, 9999))
        return f"{a}-{b}-{c}"

    def _fake_credit_card(self, original: str, rng: random.Random) -> str:
        """Generate a 16-digit Luhn-valid number."""
        digits = [rng.randint(0, 9) for _ in range(15)]
        total = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        check = (10 - (total % 10)) % 10
        all_digits = digits + [check]
        s = "".join(map(str, all_digits))
        return f"{s[:4]} {s[4:8]} {s[8:12]} {s[12:]}"

    def _fake_dob(self, original: str, rng: random.Random) -> str:
        from datetime import date, timedelta
        days_back = rng.randint(25 * 365, 70 * 365)
        dob = date.today() - timedelta(days=days_back)
        return dob.strftime("%d/%m/%Y")

    def _fake_ip(self, original: str, rng: random.Random) -> str:
        prefix = rng.choice(["10", "172.16", "192.168"])
        if prefix == "10":
            return f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
        elif prefix == "172.16":
            return f"172.{rng.randint(16,31)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
        else:
            return f"192.168.{rng.randint(0,255)}.{rng.randint(1,254)}"

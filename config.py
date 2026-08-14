REDACT_LABELS = {
    "PERSON",
    "EMAIL",
    "PHONE",
    "COMPANY",
    "ADDRESS",
    "SSN",
    "CREDIT_CARD",
    "DOB",
    "IP",
}

KEEP_LABELS = {
    "MONEY",
    "PERCENTAGE",
    "DATE",
    "LOCATION",
    "DOCUMENT_NUMBER",
    "FINANCIAL_FIGURE",
}

# Minimum detection_confidence to consider an entity at all
DETECTION_THRESHOLD = 0.45

# If agreement=False and detection_confidence below this, mark as REVIEW
REVIEW_THRESHOLD = 0.60

# Label normalization — maps raw model labels to our vocabulary
LABEL_MAP = {
    # PERSON
    "first_name":        "PERSON",
    "last_name":         "PERSON",
    "full_name":         "PERSON",
    "person":            "PERSON",
    "PERSON":            "PERSON",
    "PER":               "PERSON",

    # COMPANY
    "company_name":      "COMPANY",
    "organization":      "COMPANY",
    "ORGANIZATION":      "COMPANY",
    "COMPANY":           "COMPANY",
    "ORG":               "COMPANY",

    # EMAIL
    "email":             "EMAIL",
    "EMAIL":             "EMAIL",
    "email_address":     "EMAIL",

    # PHONE
    "phone":             "PHONE",
    "PHONE":             "PHONE",
    "phone_number":      "PHONE",
    "fax_number":        "PHONE",

    # ADDRESS
    "address":           "ADDRESS",
    "ADDRESS":           "ADDRESS",
    "street_address":    "ADDRESS",
    "mailing_address":   "ADDRESS",
    "location":          "ADDRESS",
    "LOCATION":          "ADDRESS",

    # SSN
    "ssn":               "SSN",
    "SSN":               "SSN",
    "national_id":       "SSN",
    "NATIONAL_ID":       "SSN",
    "social_security":   "SSN",

    # CREDIT_CARD
    "card_number":       "CREDIT_CARD",
    "CARD_NUMBER":       "CREDIT_CARD",
    "credit_card":       "CREDIT_CARD",
    "CREDIT_CARD":       "CREDIT_CARD",

    # DOB
    "date_of_birth":     "DOB",
    "DOB":               "DOB",
    "birthdate":         "DOB",
    "BIRTHDATE":         "DOB",
    "dob":               "DOB",

    # IP
    "ipv4":              "IP",
    "ipv6":              "IP",
    "ip":                "IP",
    "IP":                "IP",
    "ip_address":        "IP",
}

# Context keywords that boost context_confidence
DOB_CONTEXT_KEYWORDS = [
    "date of birth",
    "dob",
    "born on",
    "birth date",
    "d.o.b",
]

ADDRESS_CONTEXT_KEYWORDS = [
    "registered office",
    "corporate office",
    "mailing address",
    "address",
    "located at",
    "office at",
]

PERSON_CONTEXT_KEYWORDS = [
    "contact person",
    "name",
    "director",
    "promoter",
    "signed by",
    "authorised by",
    "company secretary",
]

COMPANY_CONTEXT_KEYWORDS = [
    "company",
    "incorporated",
    "limited",
    "ltd",
    "pvt",
    "llp",
]
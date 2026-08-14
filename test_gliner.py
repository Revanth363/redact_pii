"""Quick smoke-test for GLiNER model."""
import warnings
warnings.filterwarnings("ignore")

from gliner import GLiNER

print("Loading urchade/gliner_multi_pii-v1 ...")
model = GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")
print("Model loaded OK")

text = (
    "Sarthak Malvadkar is Company Secretary at KSH International Limited. "
    "Email: cs.connect@kshinternational.com  Phone: +91 20 45053237. "
    "Registered at 11/3, Village Birdewadi, Chakan, Pune - 410501."
)

labels = ["person", "organization", "email address", "phone number", "address", "date of birth"]

entities = model.predict_entities(text, labels, threshold=0.45)

print(f"\nFound {len(entities)} entities:")
for e in entities:
    print(f"  [{e['label']:20s}]  {e['text']:40s}  score={e['score']:.3f}")

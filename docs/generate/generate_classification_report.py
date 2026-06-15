"""Generate combined Photo + Audio Classification modelling PDF report.

Focuses on the *modelling* design behind both classifiers — data sourcing,
class balancing, preprocessing, architecture choices, training config, and
results — plus the shared three-pass escalation pattern and H3 risk
enrichment that ties them into the wider Marine Risk Mapping stack.

Output: docs/pdfs/classification_modelling.pdf
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

# ── Paths ────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "docs" / "pdfs" / "modelling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "classification_modelling.pdf"

AUDIO_ART = ROOT / "data" / "processed" / "ml" / "artifacts" / "audio_classifier"
PHOTO_ART = ROOT / "data" / "processed" / "ml" / "artifacts" / "photo_classifier"
AUDIO_DIAGRAMS = AUDIO_ART / "diagrams"


# ═══════════════════════════════════════════════════════════════
# PDF Class — navy / teal theme (matches earlier reports)
# ═══════════════════════════════════════════════════════════════


class ReportPDF(FPDF):
    NAVY = (15, 32, 65)
    TEAL = (0, 150, 136)
    LIGHT_BG = (240, 245, 250)
    WHITE = (255, 255, 255)
    DARK_TEXT = (30, 30, 30)
    MID_TEXT = (80, 80, 80)
    ACCENT_GREEN = (46, 204, 113)
    ACCENT_AMBER = (243, 156, 18)
    ACCENT_BLUE = (52, 152, 219)
    ACCENT_RED = (214, 64, 69)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(
                0,
                10,
                "Marine Risk Mapping -- Photo & Audio Classification Modelling",
                align="C",
            )
            self.ln(4)
            self.set_draw_color(*self.TEAL)
            self.set_line_width(0.3)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.MID_TEXT)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.NAVY)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.TEAL)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(4)

    def subsection_title(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.TEAL)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def small_text(self, text: str):
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.MID_TEXT)
        self.multi_cell(0, 4.5, text)
        self.ln(1)

    def bullet(self, text: str, indent: int = 15):
        x = self.get_x()
        self.set_x(x + indent - 5)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.TEAL)
        self.cell(5, 5.5, "-")
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def callout_box(
        self,
        title: str,
        body: str,
        colour: tuple[int, int, int] | None = None,
    ):
        if colour is None:
            colour = self.TEAL
        x0 = 10
        y0 = self.get_y()
        # Pre-measure body height
        self.set_font("Helvetica", "", 9.5)
        # rough estimate: 5mm per line, multi_cell width 178
        body_lines = max(1, len(body) // 95 + body.count("\n"))
        h = 10 + body_lines * 5
        self.set_fill_color(*self.LIGHT_BG)
        self.rect(x0, y0, 190, h, style="F")
        self.set_fill_color(*colour)
        self.rect(x0, y0, 3, h, style="F")
        self.set_xy(x0 + 6, y0 + 2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*colour)
        self.cell(0, 5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_x(x0 + 6)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*self.DARK_TEXT)
        self.multi_cell(178, 5, body)
        self.set_y(y0 + h + 3)

    def metric_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        col_widths: list[int] | None = None,
    ):
        if col_widths is None:
            col_widths = [190 // len(headers)] * len(headers)
        self.set_fill_color(*self.NAVY)
        self.set_text_color(*self.WHITE)
        self.set_font("Helvetica", "B", 9)
        for w, h_text in zip(col_widths, headers, strict=False):
            self.cell(w, 7, f"  {h_text}", fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for i, row in enumerate(rows):
            bg = self.LIGHT_BG if i % 2 == 0 else self.WHITE
            self.set_fill_color(*bg)
            for j, (w, cell_val) in enumerate(
                zip(col_widths, row, strict=False)
            ):
                if j == 0:
                    self.set_text_color(*self.DARK_TEXT)
                else:
                    self.set_text_color(*self.TEAL)
                self.cell(w, 7, f"  {cell_val}", fill=True)
            self.ln()
        self.ln(3)

    def stat_boxes(self, stats: list[tuple]):
        y = self.get_y()
        n = len(stats)
        box_w = 42
        gap = 4
        x_start = 10 + (190 - (box_w * n + gap * (n - 1))) / 2
        for i, (value, label) in enumerate(stats):
            x = x_start + i * (box_w + gap)
            self.set_fill_color(*self.LIGHT_BG)
            self.rect(x, y, box_w, 22, style="F")
            self.set_xy(x, y + 3)
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*self.TEAL)
            self.cell(box_w, 8, str(value), align="C")
            self.set_xy(x, y + 12)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(box_w, 6, label, align="C")
        self.set_y(y + 26)

    def add_image_safe(self, path, w=None, caption=None):
        p = Path(path)
        if not p.exists():
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.ACCENT_AMBER)
            self.cell(
                0,
                5,
                f"[Image not found: {p.name}]",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            return
        if w is None:
            w = 170
        if self.get_y() + 60 > 270:
            self.add_page()
        x = 10 + (190 - w) / 2
        self.image(str(p), x=x, w=w)
        if caption:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*self.MID_TEXT)
            self.cell(0, 5, caption, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)


# ═══════════════════════════════════════════════════════════════
# Cover page
# ═══════════════════════════════════════════════════════════════


def render_cover(pdf: ReportPDF) -> None:
    pdf.add_page()
    pdf.set_fill_color(*pdf.NAVY)
    pdf.rect(0, 0, 210, 90, style="F")
    pdf.set_text_color(*pdf.WHITE)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_xy(10, 28)
    pdf.cell(0, 12, "Whale Species Classification", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 14)
    pdf.set_xy(10, 44)
    pdf.cell(
        0,
        8,
        "Modelling design for photo + audio identification",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", "I", 11)
    pdf.set_xy(10, 56)
    pdf.cell(
        0,
        7,
        "Marine Risk Mapping -- modelling drill report",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_y(100)
    pdf.set_text_color(*pdf.DARK_TEXT)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.multi_cell(
        0,
        5.8,
        "This report covers the two end-user classification models that "
        "power citizen-science sighting reports: a single-stage CNN for "
        "photos (EfficientNet-B4) and a dual XGBoost/CNN audio "
        "classifier built on mel-spectrogram + acoustic features. The "
        "codebase is designed around a three-pass escalation cascade "
        "(critical / broad / rare) for each modality, but only the "
        "first pass - the ESA critical-species model - is trained and "
        "deployed in v1 production. Passes 2 and 3, plus an ArcFace "
        "alternative architecture for photos, are fully coded and ship-"
        "ready but awaiting training. Predictions are joined to the "
        "same H3-cell collision-risk lookup used elsewhere in the "
        "platform.",
    )
    pdf.ln(4)

    pdf.set_y(146)
    pdf.stat_boxes(
        [
            ("8 + 8", "Critical species (photo / audio)"),
            ("99.3%", "Audio CNN accuracy"),
            ("89%", "Photo accuracy"),
            ("1 / 3", "Cascade passes live"),
        ]
    )

    pdf.ln(6)
    pdf.subsection_title("Report contents")
    pdf.bullet(
        "Shared design: cascade pattern, production vs designed-but-unbuilt"
    )
    pdf.bullet("Audio: data, preprocessing, balancing, XGBoost vs CNN")
    pdf.bullet(
        "Photo: data, EfficientNet-B4 softmax + ArcFace alternative"
    )
    pdf.bullet("Per-class results and confusion-matrix diagnostics")
    pdf.bullet("H3 risk enrichment + FastAPI integration")
    pdf.bullet("Production status, roadmap, and modelling trade-offs")


# ═══════════════════════════════════════════════════════════════
# Section 1: Shared design
# ═══════════════════════════════════════════════════════════════


def render_shared_design(pdf: ReportPDF) -> None:
    pdf.add_page()
    pdf.section_title("1. Shared design")

    pdf.subsection_title("Why two modalities")
    pdf.body_text(
        "A citizen-science sighting is often noisy: blurry photos, distant "
        "blows, surface-only views, or audio recorded from a hydrophone "
        "with no visual at all. Treating photo and audio as separate "
        "classifiers (rather than a fused model) keeps each one trainable "
        "from the public datasets that exist (Happywhale for photos, "
        "Watkins + Zenodo for audio) and lets users contribute whichever "
        "modality they have. The sighting-report endpoint accepts either "
        "or both and reconciles the species predictions downstream."
    )

    pdf.subsection_title("Three-pass escalation cascade (designed)")
    pdf.body_text(
        "Each classifier is designed as a cascade of three models trained "
        "on progressively wider species sets. The cascade exists because "
        "the critical seven ESA-listed species drive almost all collision-"
        "risk signal, but a sighting could be of any cetacean. Forcing a "
        "single 30-class model dilutes accuracy on the species that "
        "matter; gating with a confidence-driven escalation is meant to "
        "give the best of both worlds. The pattern is the same for "
        "audio and photos."
    )

    pdf.metric_table(
        headers=["Pass", "Classes", "Trigger to escalate", "Status"],
        rows=[
            [
                "Critical",
                "7-8 ESA + other_cetacean",
                "top == other OR conf < 0.65",
                "Live",
            ],
            [
                "Broad",
                "~19 non-critical + unknown",
                "top == unknown OR conf < 0.50",
                "Coded, not trained",
            ],
            [
                "Rare",
                "Cosine-similarity gallery",
                "Always last resort",
                "Coded, no gallery",
            ],
        ],
        col_widths=[25, 60, 65, 40],
    )

    pdf.callout_box(
        "What 'designed but not deployed' means in practice",
        "The wrapper classes TwoPassPhotoClassifier and "
        "ThreePassAudioClassifier exist in pipeline/{photo,audio}/"
        "classify.py and route through critical -> broad -> rare with "
        "the escalation rules above. The class lists, training flags "
        "(--stage broad / --stage rare), config constants "
        "(PHOTO_BROAD_MODEL_DIR, AUDIO_BROAD_CONFIDENCE_THRESHOLD, etc.) "
        "and Pydantic response schemas are all in place. What is missing "
        "is (a) the broad model weights, (b) the rare embedding gallery, "
        "and (c) swapping the backend service from "
        "WhalePhotoClassifier.load() to the wrapper. Each is a half-day "
        "of work; the cascade was deferred because v1 needed a working "
        "end-to-end product, not a complete one.",
        colour=pdf.ACCENT_AMBER,
    )

    pdf.callout_box(
        "Why a gatekeeper class instead of just a confidence threshold",
        "A vanilla 7-class model is forced to allocate probability mass "
        "among the seven species even when shown a dolphin. Confidence "
        "scores stay high (75-95%) and the model confidently predicts "
        "the wrong critical species. Adding 'other_cetacean' as an "
        "explicit gatekeeper class - trained on a stratified sample of "
        "~3.8k non-target Happywhale images - lets the model learn to "
        "say 'not one of these seven' as a positive output, which is "
        "much more reliable than thresholding. Until the broad model is "
        "trained, an 'other_cetacean' verdict is the final answer that "
        "reaches the user - they see 'Cetacean (not one of the seven "
        "critical species)' rather than a finer ID.",
        colour=pdf.TEAL,
    )

    pdf.subsection_title("Spatial enrichment")
    pdf.body_text(
        "Both classifiers accept optional (lat, lon). When provided, the "
        "prediction is joined to the H3 res-7 cell containing the point "
        "and returned alongside that cell's seven sub-scores from "
        "fct_collision_risk. This is what lets the frontend tell a user "
        "'right whale, 87 percent, cell in top 5% strike risk this "
        "season' without a second API call. Photos can carry EXIF GPS; "
        "audio requires user-supplied coordinates."
    )


# ═══════════════════════════════════════════════════════════════
# Section 2: Audio modelling
# ═══════════════════════════════════════════════════════════════


def render_audio_section(pdf: ReportPDF) -> None:
    pdf.add_page()
    pdf.section_title("2. Audio classification")

    pdf.subsection_title("Target species and data sources")
    pdf.body_text(
        "Eight target species: right, humpback, fin, blue, sperm, minke, "
        "sei, and killer whale. Training data is pooled from four public "
        "databases - Watkins Marine Mammal Sound Database (most species), "
        "plus three Zenodo deposits for fine-grained call types."
    )

    pdf.metric_table(
        headers=["Source", "Coverage", "Files"],
        rows=[
            ["Watkins", "All 8 species (bundle per species)", "~370"],
            ["Zenodo 3624145", "Blue whale D / Z calls", "4"],
            ["Zenodo 4293955", "Humpback song units", "65"],
            ["Zenodo 8147524", "Fin whale 20 Hz pulses", "13"],
        ],
        col_widths=[55, 100, 35],
    )

    pdf.body_text(
        "Raw file counts are wildly imbalanced (sei = 1 file, killer = "
        "179 files) but segment-level balancing fixes this downstream."
    )

    pdf.subsection_title("Preprocessing pipeline")
    pdf.body_text(
        "Each file goes through: load -> resample to 16 kHz mono -> "
        "segment into 4-second windows with 2-second hop (50% overlap) "
        "-> per-segment mel spectrogram (128 mels, FFT 2048, hop 512, "
        "fmin 10 Hz, fmax 8 kHz) AND a 64-dim acoustic feature vector "
        "(20 MFCCs mean+std, spectral centroid, bandwidth, rolloff, "
        "flatness, 7-band contrast, ZCR, RMS, dominant frequency, "
        "envelope statistics)."
    )
    pdf.body_text(
        "fmin = 10 Hz is deliberate: blue whales call below 20 Hz, "
        "below the audible range of most listeners. fmax = 8 kHz covers "
        "all baleen whale calls and most odontocete clicks."
    )

    pdf.subsection_title("Three-stage class balancing")
    pdf.bullet(
        "Segment cap (2000): prevents killer whale (179 files -> would "
        "be ~20k segments) from dominating gradient updates."
    )
    pdf.bullet(
        "Augmentation target (500): species with <500 raw segments are "
        "padded up to 500 via time-stretch (rate 0.9-1.1), pitch-shift "
        "(+-2 semitones), and additive noise (SNR 15-30 dB)."
    )
    pdf.bullet(
        "Inverse-frequency class weights: applied to the loss function "
        "as w_c = N / (C * n_c) so any remaining imbalance is corrected "
        "at the loss level."
    )

    pdf.add_image_safe(
        AUDIO_DIAGRAMS / "segment_distribution.png",
        w=160,
        caption=(
            "Segment distribution after balancing - raw (teal) vs "
            "augmented (amber), with the 500 floor and 2000 cap marked."
        ),
    )

    pdf.subsection_title("Two backends: XGBoost vs CNN")
    pdf.body_text(
        "Both backends are trained on the same segment dataset. XGBoost "
        "operates on the 64-dim acoustic feature vector with 5-fold "
        "stratified CV. The CNN is a ResNet18 trained on mel-spectrogram "
        "images (128 x ~125) on Apple MPS, with early stopping on "
        "validation macro F1 (patience = 7 epochs). The CNN is the "
        "deployed critical-pass model; XGBoost remains in the codebase "
        "as a diagnostic baseline and rapid-iteration target."
    )

    pdf.metric_table(
        headers=["Backend", "Accuracy", "Macro F1", "Wall time", "Notes"],
        rows=[
            [
                "XGBoost",
                "97.9%",
                "98.2%",
                "214 s",
                "Weak on blue/fin split (F1 ~0.95)",
            ],
            [
                "CNN (ResNet18)",
                "99.3%",
                "99.4%",
                "280 s",
                "Best at epoch 5, early-stopped @ 12",
            ],
        ],
        col_widths=[35, 28, 28, 28, 71],
    )

    pdf.callout_box(
        "Why CNN wins on fin vs blue",
        "Both species call in the 15-30 Hz band, and XGBoost's spectral "
        "shape features (rolloff, flatness) collapse that band to a few "
        "scalars. The CNN sees the full time-frequency image and learns "
        "the call-pattern signature: fin whale 20 Hz pulses are short "
        "and regular (~12s interval), blue whale D-calls are longer "
        "FM sweeps. That is structure XGBoost cannot easily learn from "
        "summary statistics.",
        colour=pdf.ACCENT_BLUE,
    )

    pdf.add_image_safe(
        AUDIO_ART / "confusion_matrix.png",
        w=170,
        caption="Audio CNN confusion matrix (validation segments).",
    )

    pdf.add_image_safe(
        AUDIO_ART / "feature_importance.png",
        w=170,
        caption=(
            "XGBoost top features: spectral_rolloff_mean, "
            "spectral_flatness_mean, MFCC moments dominate."
        ),
    )


# ═══════════════════════════════════════════════════════════════
# Section 3: Photo modelling
# ═══════════════════════════════════════════════════════════════


def render_photo_section(pdf: ReportPDF) -> None:
    pdf.add_page()
    pdf.section_title("3. Photo classification")

    pdf.subsection_title("Target species and data sources")
    pdf.body_text(
        "Seven target species plus an other_cetacean gatekeeper. Sperm "
        "whale is dropped from the photo critical class - deep divers "
        "are rarely surface-photographed with identifiable features, "
        "and the Happywhale Kaggle dataset has no sperm whale records. "
        "All training data comes from the public Happywhale & Dolphin "
        "competition (~51k images, 30 species)."
    )

    pdf.metric_table(
        headers=["Pass", "Species", "Approx. images after filtering"],
        rows=[
            ["Critical (live)", "7 target + other_cetacean", "~20k (capped)"],
            ["Broad (planned)", "18 non-critical + unknown", "~32k available"],
            [
                "Rare (planned)",
                "1 (frasiers_dolphin)",
                "14 (embedding gallery)",
            ],
        ],
        col_widths=[40, 75, 75],
    )

    pdf.subsection_title("Known label fixes")
    pdf.body_text(
        "Happywhale ships with a handful of typos and lumped categories "
        "that have to be corrected before filtering:"
    )
    pdf.bullet("globis -> short_finned_pilot_whale")
    pdf.bullet("pilot_whale -> short_finned_pilot_whale")
    pdf.bullet("kiler_whale -> killer_whale")
    pdf.bullet("bottlenose_dolpin -> bottlenose_dolphin")
    pdf.bullet(
        "southern_right_whale -> right_whale  (collapses geographic "
        "subspecies into one ESA species)"
    )

    pdf.subsection_title("Single-stage vs two-stage design")
    pdf.body_text(
        "An obvious alternative is a two-stage pipeline: a body-part "
        "detector (fluke / dorsal / flank / head) followed by a "
        "view-conditioned species head. We chose single-stage because "
        "(a) Happywhale has no view annotations, so two-stage would "
        "require manual labelling of thousands of crops; (b) species "
        "is a much coarser target than the original Kaggle competition "
        "(15k-class individual re-identification), so view-invariance "
        "is learnable from the data; (c) the dropout(0.4) + label "
        "smoothing(0.1) regularisation we use empirically handles the "
        "view variation well."
    )

    pdf.callout_box(
        "Why EfficientNet-B4",
        "B4 hits the accuracy/parameter sweet spot for fine-grained "
        "image classification - 19M params (vs ResNet50's 25M), 380px "
        "native input, and ImageNet-pretrained weights are shipped with "
        "torchvision. We downsized to 224px in production to fit larger "
        "batches (64 vs 32) on Apple MPS without sacrificing measurable "
        "accuracy.",
        colour=pdf.TEAL,
    )

    pdf.subsection_title("ArcFace alternative (built, not trained)")
    pdf.body_text(
        "A second photo-classification path lives alongside the softmax "
        "model: pipeline/photo/arcface_classify.py implements the "
        "1st-place Kaggle Happywhale architecture (Abe & Yamaguchi, "
        "2022) - sub-centre ArcFace head (k=2), Generalised Mean (GeM) "
        "multi-scale pooling, dynamic per-class margins, gallery-KNN "
        "inference. It is a drop-in replacement for the softmax "
        "classifier at any cascade slot, not a separate pass."
    )

    pdf.metric_table(
        headers=["Feature", "Softmax (live)", "ArcFace (built)"],
        rows=[
            ["Backbone", "EfficientNet-B4, 224px", "EfficientNet-B7, 448px"],
            ["Head", "Linear(1792, 8) + dropout", "Sub-centre ArcFace, k=2"],
            ["Pooling", "Global average", "GeM, last two stages"],
            ["Margin", "None (CE loss)", "Dynamic ~ n_samples^-0.5"],
            ["Inference", "Direct softmax", "Logit x 0.5 + KNN x 0.5"],
            ["Training cost", "~30 min, Apple MPS", "GPU only (~6-12 h)"],
            ["Status", "Trained, deployed", "Coded, not trained"],
        ],
        col_widths=[50, 65, 75],
    )

    pdf.callout_box(
        "Why ArcFace was deferred and what would unlock it",
        "The architecture is the V2 upgrade path. Three concrete wins "
        "for fine-grained whale ID: (1) sub-centre k=2 absorbs the "
        "fluke / dorsal / flank multi-modality cleanly in embedding "
        "space; (2) dynamic margins push rare species apart "
        "aggressively (~180x imbalance in Happywhale); (3) gallery-KNN "
        "blend improves open-set robustness for species the model has "
        "never seen. Deferred because EfficientNet-B7 at 448px does not "
        "fit Apple MPS in any reasonable wall-clock. A remote-training "
        "harness already exists (pipeline/analysis/train_arcface_remote.py "
        "+ setup_ec2_gpu.sh) that provisions a CUDA EC2 instance, rsyncs "
        "images + script, runs training, and pulls the model + KNN "
        "gallery back. The blocker is GPU budget, not engineering work.",
        colour=pdf.ACCENT_BLUE,
    )

    pdf.subsection_title("Preprocessing and augmentations")
    pdf.bullet(
        "Resize to 224 x 224 (downsized from B4-native 380 for throughput)"
    )
    pdf.bullet(
        "ImageNet normalisation: mean (0.485, 0.456, 0.406), "
        "std (0.229, 0.224, 0.225)"
    )
    pdf.bullet("Training: random horizontal flip, random rotation +-15 deg,")
    pdf.bullet(
        "color jitter (brightness=contrast=saturation=0.2), "
        "random resized crop (0.8-1.0)"
    )
    pdf.bullet("Validation: center crop + normalize only")

    pdf.subsection_title("Class balancing")
    pdf.body_text(
        "Mirrors the audio approach but at the image level. Per-species "
        "image cap of 5000 prevents humpback (dominant in Happywhale) "
        "from drowning rare classes. The other_cetacean class is built "
        "by stratified sampling of up to 250 images per non-target "
        "species, giving the model diverse rejection examples. A "
        "weighted random sampler in the DataLoader balances batches, "
        "and label smoothing 0.1 in CrossEntropyLoss regularises "
        "overconfident predictions on sparse species (sei, blue)."
    )

    pdf.subsection_title("Training config")
    pdf.metric_table(
        headers=["Hyperparameter", "Value", "Rationale"],
        rows=[
            ["Optimizer", "AdamW", "Decoupled weight decay"],
            ["LR (head)", "1e-4", "Trainable from scratch"],
            ["LR (backbone)", "1e-5", "10x lower - pretrained"],
            ["Scheduler", "CosineAnnealingLR", "T_max = epochs"],
            ["Backbone warmup", "2 epochs frozen", "Stabilise head first"],
            ["Batch size", "64", "Apple MPS, ~6 GB"],
            ["Max epochs", "30", "Early stop on val F1"],
            ["Early-stop patience", "7", "Same as audio CNN"],
            ["Label smoothing", "0.1", "Regularises rare classes"],
        ],
        col_widths=[55, 50, 85],
    )


def render_photo_results(pdf: ReportPDF) -> None:
    pdf.add_page()
    pdf.section_title("4. Photo results")

    pdf.subsection_title("Headline metrics")
    pdf.stat_boxes(
        [
            ("89%", "Accuracy"),
            ("0.87", "Macro F1"),
            ("0.90", "Weighted F1"),
            ("4054", "Val images"),
        ]
    )

    pdf.subsection_title("Per-class metrics (validation)")
    pdf.metric_table(
        headers=["Species", "Precision", "Recall", "F1", "Support"],
        rows=[
            ["blue_whale", "0.96", "0.99", "0.97", "966"],
            ["fin_whale", "0.72", "0.82", "0.77", "265"],
            ["humpback_whale", "0.95", "0.82", "0.88", "1000"],
            ["killer_whale", "0.97", "0.91", "0.94", "491"],
            ["minke_whale", "0.75", "0.88", "0.81", "322"],
            ["other_cetacean", "0.87", "0.86", "0.86", "751"],
            ["right_whale", "0.93", "0.98", "0.96", "173"],
            ["sei_whale", "0.67", "0.99", "0.80", "86"],
        ],
        col_widths=[55, 35, 30, 30, 40],
    )

    pdf.callout_box(
        "Where the photo model struggles",
        "Sei whale precision is 0.67 with recall 0.99: the model "
        "confidently labels things as sei even when they aren't, "
        "because the species has only 86 validation examples and looks "
        "visually similar to fin and minke from a typical surface "
        "photo (single ridge, sickle dorsal, dark grey). Fin whale "
        "F1 of 0.77 reflects the same baleen-whale confusion. Critical "
        "ESA species we care most about - blue, right, killer, "
        "humpback - all sit at F1 >= 0.88.",
        colour=pdf.ACCENT_AMBER,
    )

    pdf.add_image_safe(
        PHOTO_ART / "confusion_matrix.png",
        w=170,
        caption=(
            "Photo classifier confusion matrix - off-diagonal mass "
            "concentrated in baleen-whale lookalikes."
        ),
    )


# ═══════════════════════════════════════════════════════════════
# Section 5: Integration + takeaways
# ═══════════════════════════════════════════════════════════════


def render_integration(pdf: ReportPDF) -> None:
    pdf.add_page()
    pdf.section_title("5. Integration with the platform")

    pdf.subsection_title("FastAPI endpoints")
    pdf.metric_table(
        headers=["Endpoint", "Inputs", "Returns"],
        rows=[
            [
                "POST /api/v1/photo/classify",
                "image + optional (lat, lon)",
                "top species + runner-ups + risk context",
            ],
            [
                "POST /api/v1/audio/classify",
                "audio + required (lat, lon)",
                "per-segment preds + dominant + risk context",
            ],
            [
                "POST /api/v1/sightings/report",
                "image + audio + species guess",
                "merged assessment + advisory",
            ],
        ],
        col_widths=[60, 60, 70],
    )

    pdf.callout_box(
        "What the API actually calls today",
        "backend/services/photo.py calls WhalePhotoClassifier.load() "
        "directly, not TwoPassPhotoClassifier; backend/services/audio.py "
        "calls WhaleAudioClassifier.load() directly, not the three-pass "
        "wrapper. So a low-confidence or other_cetacean verdict is "
        "returned to the user as-is, without escalation. Wiring the "
        "cascade in is a ~10-line change once the broad weights exist.",
        colour=pdf.ACCENT_AMBER,
    )

    pdf.subsection_title("Lazy-loaded singletons")
    pdf.body_text(
        "Both classifiers are wrapped as lazy singletons in "
        "backend/services/{photo,audio}.py - the model weights load on "
        "the first request, not at FastAPI startup. This keeps boot "
        "time fast (the EfficientNet-B4 checkpoint alone is ~75 MB) "
        "and lets the API serve risk-only traffic without paying the "
        "ML import cost."
    )

    pdf.callout_box(
        "Why route handlers are sync (def, not async def)",
        "All classifier inference is synchronous CPU/GPU work. An "
        "'async def' handler would block the event loop. FastAPI "
        "automatically offloads plain 'def' handlers to its thread "
        "pool, which keeps the server responsive to other requests "
        "while inference is running. Rate limits are 10/min on "
        "classify, 20/min on sighting reports.",
        colour=pdf.ACCENT_BLUE,
    )

    pdf.subsection_title("Spatial enrichment query")
    pdf.body_text(
        "Once the classifier emits a species + confidence and the "
        "client provides (lat, lon), the service: (1) computes the H3 "
        "res-7 cell with h3.latlng_to_cell(lat, lon, 7); (2) queries "
        "fct_collision_risk WHERE h3_cell = %s; (3) returns the seven "
        "sub-scores and risk category alongside the species result. "
        "The same join is used by the standalone /risk/zones/{h3_cell} "
        "endpoint, so there is one source of truth for cell context."
    )


def render_takeaways(pdf: ReportPDF) -> None:
    pdf.add_page()
    pdf.section_title("6. Production status and takeaways")

    pdf.subsection_title("Production status at a glance")
    pdf.metric_table(
        headers=["Component", "Status", "What is missing"],
        rows=[
            [
                "Photo critical (EffNet-B4, 8 cls)",
                "Deployed",
                "-",
            ],
            [
                "Photo broad (EffNet-B4, 19 cls)",
                "Coded",
                "~30 min training run",
            ],
            [
                "Photo rare (cosine gallery)",
                "Coded",
                "Gallery build pass",
            ],
            [
                "Photo ArcFace (alt architecture)",
                "Coded",
                "GPU + 6-12 h training",
            ],
            [
                "Audio critical (CNN, 8 cls)",
                "Deployed",
                "-",
            ],
            [
                "Audio broad (~15 cls)",
                "Coded",
                "More training data",
            ],
            [
                "Audio rare (embedding KNN)",
                "Coded",
                "Gallery build pass",
            ],
            [
                "Cascade wired into API",
                "Not wired",
                "Swap .load() in 2 services",
            ],
        ],
        col_widths=[70, 35, 85],
    )

    pdf.subsection_title("Modelling decisions worth defending")
    pdf.bullet(
        "Gatekeeper classes (other_cetacean, unknown_cetacean) beat raw "
        "confidence thresholds because they let the model express "
        "'none of the above' as a positive learned output."
    )
    pdf.bullet(
        "CNN beats XGBoost for audio (99.3% vs 97.9%) specifically on "
        "fin/blue whale - the spectro-temporal structure of calls is "
        "not capturable by summary statistics."
    )
    pdf.bullet(
        "Single-stage CNN works for photos because species is a much "
        "coarser target than individual re-identification; view "
        "invariance is learnable end-to-end."
    )
    pdf.bullet(
        "Segment-level balancing is the right unit for audio - the "
        "raw file count is meaningless when one file can be 20 minutes "
        "and another 3 seconds."
    )
    pdf.bullet(
        "Designing the cascade up front (config constants, wrapper "
        "classes, training flags) means activating it is a swap, not "
        "a rewrite - the v1 trade-off was 'train fewer models', not "
        "'redesign later'."
    )

    pdf.subsection_title("Trade-offs to flag")
    pdf.bullet(
        "Without the broad pass, every non-critical cetacean comes back "
        "as 'other_cetacean' - the user gets no finer ID for a dolphin "
        "or pilot whale. That is acceptable for risk routing (none of "
        "those are ESA-listed) but is a UX hole."
    )
    pdf.bullet(
        "Photo model is weaker on baleen-whale lookalikes (fin, sei, "
        "minke F1 between 0.77-0.81). Acceptable because critical "
        "ESA species (blue, right, humpback, killer) all score "
        ">= 0.88, but should be revisited if Happywhale or NOAA "
        "release more labelled photos."
    )
    pdf.bullet(
        "Audio CNN was early-stopped at epoch 12 with best weights "
        "from epoch 5 - aggressive overfitting on the small dataset. "
        "Patience could be tightened further."
    )
    pdf.bullet(
        "Both models lean on data augmentation to compensate for "
        "imbalance; this risks the model learning the augmentations "
        "rather than the species. Holding raw-only validation sets is "
        "essential and is already enforced in the train/val split."
    )
    pdf.bullet(
        "Softmax vs ArcFace is not measured head-to-head yet - the "
        "choice to ship softmax was driven by training cost (Apple MPS "
        "vs CUDA), not measured accuracy. An A/B comparison is the "
        "first thing the ArcFace training run buys us."
    )

    pdf.subsection_title("Roadmap (in priority order)")
    pdf.bullet(
        "Train photo broad model (~30 min) and rare embedding gallery; "
        "swap WhalePhotoClassifier -> TwoPassPhotoClassifier in "
        "backend/services/photo.py."
    )
    pdf.bullet(
        "Same activation for audio - the wrapper and config are already "
        "in place."
    )
    pdf.bullet(
        "Train ArcFace critical model on a CUDA EC2 box via the "
        "existing train_arcface_remote.py harness; A/B against softmax "
        "on a held-out test set; promote whichever wins per species."
    )
    pdf.bullet(
        "Replace the audio CNN's ResNet18 with a YAMNet or PANN "
        "backbone pretrained on AudioSet for better low-level spectral "
        "features."
    )
    pdf.bullet(
        "Move both classifiers' weights off the VM disk to S3/R2 so the "
        "model can be retrained and hot-swapped without a redeploy."
    )

    pdf.subsection_title("Reproducibility")
    pdf.body_text(
        "All hyperparameters live in pipeline/config.py (PHOTO_* and "
        "AUDIO_* constants), so retraining is one command from project "
        "root:"
    )
    pdf.small_text(
        "  uv run python pipeline/analysis/train_audio_classifier.py "
        "[--backend cnn] [--tune]"
    )
    pdf.small_text(
        "  uv run python pipeline/analysis/train_photo_classifier.py "
        "[--tune]"
    )
    pdf.body_text(
        "Every run logs metrics, params, and artefacts to MLflow "
        "(experiments whale_audio_classifier and whale_photo). Model "
        "promotion uses pipeline/analysis/register_model.py."
    )


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.alias_nb_pages()

    render_cover(pdf)
    render_shared_design(pdf)
    render_audio_section(pdf)
    render_photo_section(pdf)
    render_photo_results(pdf)
    render_integration(pdf)
    render_takeaways(pdf)

    pdf.output(str(OUTPUT_FILE))
    print(f"Wrote {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET
import re


PPT_IN = Path("/Users/ronniesaba/Downloads/animated-healthcare-center.pptx")
PPT_OUT = Path(
    "/Users/ronniesaba/Documents/EECE503N_Project/MRI-ReportGenerator/"
    "animated-healthcare-center_project-updated.pptx"
)

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

ET.register_namespace("a", NS["a"])
ET.register_namespace("p", NS["p"])
ET.register_namespace("r", NS["r"])


SLIDE_SHAPE_UPDATES: dict[int, dict[int, list[str]]] = {
    1: {
        235: ["Automated Cervical Spine Morphometry"],
        238: ["Architecture, deployment, and validation update"],
        2: ["Application positioning: screens for physician review"],
    },
    2: {
        267: ["The Problem"],
        268: ["Manual baseline, bottlenecks, and design constraints"],
        269: ["Pipeline Architecture"],
        270: ["Segmentation, measurements, interpretation, and reporting"],
        271: ["Deployment Architecture"],
        272: ["EEP + 2 IEPs on AWS EKS with Grafana monitoring"],
        273: ["Validation"],
        274: ["What is validated, what is partial, and what is still planned"],
    },
    3: {
        288: ["The Problem"],
        289: ["01"],
    },
    4: {
        279: ["Manual reads are slow."],
    },
    5: {
        279: ["And agreement is inconsistent."],
    },
    6: {
        279: ["And honest re-validation matters."],
    },
    7: {
        288: ["The Solution"],
        289: ["02"],
    },
    8: {
        973: ["Why automate"],
        974: ["2.7-3.8 min manual baseline", "Backlogs scale poorly"],
        976: [
            "Manual agreement collapses: cord ICC 0.66, compression 0.35-0.56, "
            "Pfirrmann-cervical kappa 0.265, mixed-reader Cobb about 0.55"
        ],
        978: [
            "The pipeline must be cited, reproducible, healthy-anchored, and honest "
            "about uncertainty"
        ],
    },
    9: {
        297: ["Project objective"],
        298: [
            "Build an application-grade cervical MRI pipeline that turns one sagittal "
            "T2 exam into structured measurements, cited review flags, and a report-"
            "ready contract without pretending to diagnose disease."
        ],
    },
    10: {
        304: [
            "Input: one sagittal T2 cervical MRI. Output: a structured contract with "
            "measurements, flags, interpretations, patient fields, and report fields "
            "that a front end can render into a clinical report and PDF export."
        ],
        305: ["Project output"],
    },
    11: {
        428: ["Project principles"],
        429: ["Method"],
        430: ["Clinical stance"],
        431: [
            "Disease-agnostic, healthy-anchored measurement automation with cited "
            "thresholds and deterministic outputs."
        ],
        432: [
            "Findings are flagged for physician review, never presented as a diagnosis."
        ],
    },
    12: {
        446: ["One sagittal T2 MRI", "drives the full pipeline"],
        447: [
            "Segmentation feeds measurement groups G1-G6, which then flow into cited "
            "interpretation, a clinical report, impressions, and PDF export."
        ],
    },
    13: {
        453: ["Pipeline Architecture"],
    },
    14: {
        459: ["Core honesty line"],
        460: ['"Findings are flagged for physician review, never a diagnosis."'],
    },
    15: {
        467: ["Three segmentation", "engines"],
    },
    16: {
        475: ["Key numbers"],
        476: ["3"],
        477: ["Segmentation engines: TSS, SCT, and the SPINEPS Cobb add-on"],
        479: ["6"],
        480: ["Measurement groups", "from G1 vertebral to G6 interpretation"],
        482: ["250"],
        483: ["MMCSD cohort cases, with 49 segmented in the current validation set"],
    },
    17: {
        491: ["System composition"],
        492: ["Primary labels"],
        493: ["TSS"],
        494: ["Cord + lesion CLI"],
        495: ["SCT"],
        496: ["Cobb add-on only"],
        497: ["SPINEPS"],
        499: [
            "Gotchas: TSS and SPINEPS require separate NumPy environments; SCT must "
            "be installed or G3 should fail gracefully."
        ],
    },
    18: {
        504: ["Pipeline story"],
        505: [
            "Input: one sagittal T2 cervical MRI",
            "Segment vertebrae, discs, canal, cord, and Cobb endplates",
            "Compute G1-G5 measurements and G6 interpretation outputs",
            "Render measurements, flags, impressions, and PDF export",
        ],
    },
    19: {
        607: ["Stages in the pipeline"],
        613: ["Phase 2"],
        614: ["Input"],
        615: ["Phase 3"],
        616: ["Phase 4"],
        617: ["Runtime", "Phase 6"],
        629: ["Segmentation: TSS primary, SCT for G3/G5.1, SPINEPS for Cobb"],
        630: ["Measurements: six groups and about 16 components"],
        631: ["Interpretation: cited thresholds, status bands, and review flags"],
        632: ["Reporting: clinical report, impressions, and PDF export"],
    },
    20: {
        647: ["Our process"],
        648: ["01 Input"],
        649: ["One sagittal T2 cervical MRI enters the pipeline"],
        650: ["02 Segment"],
        651: ["TSS + SCT + SPINEPS produce the anatomical layers needed downstream"],
        652: ["03 Measure"],
        653: ["G1-G5 compute morphometry, discs, cord/canal, alignment, and screens"],
        654: ["04 Report"],
        655: [
            "G6 interpretation feeds a clinical report, impressions, and PDF export"
        ],
    },
    21: {
        699: ["Technical Specification"],
        700: ["03"],
        701: ["Segmentation, measurements, interpretation, and reporting"],
    },
    22: {
        709: ["Segmentation"],
        710: [
            "Primary segmenter: TotalSpineSeg for vertebrae, discs, and canal. "
            "Spinal Cord Toolbox supports G3 diameters and G5.1 SCIseg lesion "
            "screening. SPINEPS is a narrow Cobb add-on because its endplate sheets "
            "outperform TSS corners on cervical alignment (C6-C7 SD 5.9 degrees vs "
            "18.5 degrees, J12). Deployment gotcha: TSS and SPINEPS require separate "
            "environments, and SCT must be installed as a CLI."
        ],
    },
    23: {
        911: ["Measurement groups"],
        912: ["G1"],
        913: ["Vertebral morphometry and compression-screen geometry"],
        914: ["G2"],
        915: ["Disc height, AP ratio, signal, and bulge features"],
        916: ["G3"],
        917: ["Canal diameter, cord diameter, and SAC"],
        918: ["Cobb and alignment metrics from endplate geometry"],
        929: ["G4"],
    },
    24: {
        938: ["Measurement logic"],
        939: ["G5"],
        940: ["Fracture and myelomalacia screens"],
        941: ["G6"],
        942: ["Interpretation outputs: threshold bands and syndrome flags"],
        943: ["Inputs"],
        944: ["Group dependencies, inputs, and outputs are tracked per group"],
        945: ["Outputs"],
        946: ["About 16 components merge into measurements, flags, and interpretations"],
    },
    25: {
        1010: ["Interpretation & Reporting"],
        1018: ["Raw value to cited threshold band to status"],
        1019: ["Interpretation"],
        1020: [
            "within_reference / outside_reference / review_only with sex-specific "
            "dural-sac cut"
        ],
        1021: ["Thresholds"],
        1022: [
            "JSON contract drives the clinical report, impressions, and PDF export"
        ],
        1023: ["Reporting"],
    },
    26: {
        1031: ["AWS EKS"],
        1032: [
            "Deployed end-to-end as an application with EEP + 2 IEPs and Grafana "
            "monitoring."
        ],
    },
    27: {
        1042: ["manual read time per case"],
        1043: ["cord manual agreement"],
        1044: ["Pfirrmann-cervical agreement"],
        1045: ["2.7-3.8 min"],
        1046: ["ICC 0.66"],
        1047: ["kappa 0.265"],
    },
    28: {
        1057: ["Validation snapshot"],
        1059: ["G5.1 myelomalacia specificity"],
        1060: ["G2 disc ratio", "partial discriminator"],
        1061: ["G4 alignment is not a discriminator"],
        1062: ["G5.1"],
        1063: ["G2"],
        1064: ["G4"],
        1073: ["91%"],
        1074: ["62%"],
        1075: ["57%"],
    },
    30: {
        1093: ["Deployment architecture"],
        1094: ["Public API and orchestration layer"],
        1095: ["EEP"],
        1096: ["Runs the measurement and interpretation stack"],
        1097: ["Measurements IEP"],
        1098: ["Produces the clinical report, impressions, and PDF export"],
        1099: ["Reporting IEP"],
    },
    31: {
        1115: ["Validation by group"],
        1116: ["G1"],
        1117: ["Validated as a screen; abnormal fracture arm still untested"],
        1118: ["G2"],
        1119: ["Partial only: ratio discriminates, signal and bulge do not"],
        1120: ["G3"],
        1121: ["Strongest result: canal, cord, and SAC separate healthy vs symptomatic"],
        1122: ["G4"],
        1123: ["Reads lordosis correctly, but not a disease discriminator"],
        1124: ["G5.1"],
        1125: ["About 91% healthy specificity; sensitivity comes from the SCIseg paper"],
        1126: ["G6"],
        1127: ["Built and wired end-to-end, but not yet clinically accuracy-tested"],
    },
    32: {
        1165: ["Caveats / honesty guards"],
        1166: ["No per-case GT"],
        1167: ["Show distribution separation, not accuracy or sens/spec."],
        1168: ["G4 is limited"],
        1169: ["Do not present G4 as clinically validated."],
        1170: ["G2 is partial"],
        1171: ["Disc ratio helps; disc signal and bulge do not."],
        1172: ["Clinical stance"],
        1173: ["Outputs are screens for physician review, never diagnoses."],
    },
    33: {
        1184: ["Next validation steps"],
        1185: ["Now"],
        1186: ["G3 robustness on a random non-lesion-selected MMCSD draw"],
        1187: ["Gap"],
        1188: ["Compression-fracture arm still lacks a usable dataset"],
        1189: ["Clinical"],
        1190: ["Per-case accuracy still needs an AUBMC radiologist read"],
        1191: ["Infra"],
        1192: ["Confirm the live deployment state with the infra chat before final delivery"],
    },
    34: {
        1218: ["Monitoring & operations"],
        1219: ["AWS EKS"],
        1220: [
            "Application deployment target with EEP + 2 IEPs, Kubernetes assets, "
            "and cloud-first positioning"
        ],
        1221: ["Grafana"],
        1222: [
            "Monitoring layer for live service visibility; the infra chat owns the "
            "current runtime state"
        ],
    },
    35: {
        1229: [
            "Clinical report + impressions + PDF export. The front end renders the "
            "JSON contract into a radiologist-facing report, and the appendix can "
            "cite the two radiologist PDFs plus the validation figures."
        ],
        1232: ["Report outputs"],
    },
    36: {
        1245: [
            "Questions?",
            "Application positioning: flagged for physician review, never a diagnosis.",
        ],
    },
}


SLIDE_TEXT_SEQUENCE_UPDATES: dict[int, list[str]] = {
    29: [
        "Completed validation",
        "N / basis",
        "Verdict",
        "Key result",
        "Claim",
        "Use",
        "G3",
        "22 cases",
        "STRONG",
        "canal 11.7->8.6, SAC 4.7->2.3, cord 6.3->5.5",
        "p=.0001 / .0001 / .009",
        "Lead result",
        "G2",
        "49 cases",
        "PARTIAL",
        "ratio AUC 0.62; signal/bulge AUC 0.50",
        "p=.0018",
        "Frame carefully",
        "G4",
        "67 cases",
        "NOT discrim.",
        "d=0.28, AUC 0.57",
        "p=.32",
        "Do not overclaim",
        "G1",
        "screen only",
        "VALID screen",
        "0% healthy false-flag; null on spondylosis",
        "fracture arm untested",
        "Screen only",
        "Use the revised 2026-06-08 group-status file as the single source of truth.",
    ]
}


def find_shape(root: ET.Element, shape_id: int) -> ET.Element:
    for sp in root.findall(".//p:sp", NS):
        c_nv_pr = sp.find("p:nvSpPr/p:cNvPr", NS)
        if c_nv_pr is not None and c_nv_pr.attrib.get("id") == str(shape_id):
            return sp
    raise KeyError(f"shape id {shape_id} not found")


def set_shape_text(sp: ET.Element, paragraphs: list[str]) -> None:
    tx_body = sp.find("p:txBody", NS)
    if tx_body is None:
        raise ValueError("shape has no text body")

    existing_paragraphs = tx_body.findall("a:p", NS)
    if not existing_paragraphs:
        p = ET.SubElement(tx_body, f"{{{NS['a']}}}p")
        existing_paragraphs = [p]

    template = existing_paragraphs[0]

    for p in list(tx_body.findall("a:p", NS)):
        tx_body.remove(p)

    for text in paragraphs:
        p = deepcopy(template)
        for child in list(p):
            if child.tag in {
                f"{{{NS['a']}}}r",
                f"{{{NS['a']}}}br",
                f"{{{NS['a']}}}fld",
                f"{{{NS['a']}}}endParaRPr",
            }:
                p.remove(child)

        run = ET.SubElement(p, f"{{{NS['a']}}}r")
        r_pr = template.find("a:r/a:rPr", NS)
        if r_pr is not None:
            run.append(deepcopy(r_pr))
        else:
            ET.SubElement(run, f"{{{NS['a']}}}rPr")
        t = ET.SubElement(run, f"{{{NS['a']}}}t")
        t.text = text

        end_para = template.find("a:endParaRPr", NS)
        if end_para is not None:
            p.append(deepcopy(end_para))

        tx_body.append(p)


def apply_shape_updates(root: ET.Element, updates: dict[int, list[str]]) -> None:
    for shape_id, paragraphs in updates.items():
        sp = find_shape(root, shape_id)
        set_shape_text(sp, paragraphs)


def apply_text_sequence_updates(root: ET.Element, values: list[str]) -> None:
    text_nodes = root.findall(".//a:t", NS)
    if len(text_nodes) != len(values):
        raise ValueError(
            f"text sequence mismatch: found {len(text_nodes)} nodes, expected {len(values)}"
        )
    for node, value in zip(text_nodes, values):
        node.text = value


def update_ppt() -> None:
    PPT_OUT.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(PPT_IN, "r") as zin, ZipFile(PPT_OUT, "w", compression=ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)

            slide_match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", item.filename)
            if slide_match:
                slide_num = int(slide_match.group(1))
                if slide_num in SLIDE_SHAPE_UPDATES or slide_num in SLIDE_TEXT_SEQUENCE_UPDATES:
                    root = ET.fromstring(data)
                    if slide_num in SLIDE_SHAPE_UPDATES:
                        apply_shape_updates(root, SLIDE_SHAPE_UPDATES[slide_num])
                    if slide_num in SLIDE_TEXT_SEQUENCE_UPDATES:
                        apply_text_sequence_updates(root, SLIDE_TEXT_SEQUENCE_UPDATES[slide_num])
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)

            zout.writestr(item, data)


if __name__ == "__main__":
    update_ppt()

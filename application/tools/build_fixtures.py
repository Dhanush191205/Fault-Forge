"""Reproduce original synthetic curriculum JSON; no vendor limits or real procedures are asserted."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data"


def component(prefix, key, name, position, scale, color, sensor=None, shape="box"):
    """Build one synthetic primitive component; return config and optional illustrative sensor definition."""
    return {"id": f"{prefix}.{key}", "name": name, "sensors": [sensor] if sensor else [],
            "geometry": {"shape": shape, "position": position, "scale": scale, "color": color}}


def sensor(key, label, unit, normal, abnormal):
    """Return explicit synthetic sensor envelopes; inputs are project-authored training values only."""
    return {"id": key, "label": label, "unit": unit, "normal": normal, "abnormal": abnormal}


def question(key, text, options, correct, explanation):
    """Create a five-option authored rubric item; option identifiers do not disclose the answer."""
    return {"id": key, "text": text, "options": [{"id": f"o{i + 1}", "text": label} for i, label in enumerate(options)],
            "correct_id": f"o{correct + 1}", "explanation": explanation}


def write_pack(machine, readings, observations, diagnoses, correct, explanation):
    """Write a complete scoped synthetic training pack; preserve all safety and source provenance fields."""
    mid = machine["id"]
    steps = [
        "Review the simulated safety plan: authorized lockout/tagout, stored-energy isolation and verification before physical access.",
        "Inspect the recorded visual evidence. This simulation does not authorize access to real machinery.",
        "Read the archived condition measurements and compare them with this fixture's training envelope.",
        "Compare the recorded operating history with a competing explanation.",
        "Review the virtual verification evidence, then justify a diagnosis using the strongest observations.",
    ]
    case = {"title": observations["title"], "briefing": observations["briefing"], "manual_ids": [f"{mid}.manual.v1"],
        "component_ids": [c["id"] for c in machine["components"]], "readings": readings,
        "hints": ["Compare at least two independent observations before selecting a diagnosis.",
                  "A reading outside its training range is evidence, but does not establish a cause by itself."],
        "steps": steps, "synthetic": True,
        "diagnoses": [{"id": f"d{i + 1}", "text": label} for i, label in enumerate(diagnoses)],
        "correct_diagnosis_id": f"d{correct + 1}",
        "evidence": [{"id": f"e{i + 1}", "label": label, "text": text, "reveal_step": step}
                     for i, (label, text, step) in enumerate(observations["evidence"])],
        "required_evidence_ids": ["e1", "e2"], "explanation": explanation,
        "rationale_rubric": ["0–10: connects the two distinguishing observations to the proposed cause; partial credit for a supported but incomplete link.",
                             "0–10: compares one credible alternative and explains what evidence weakens it; no credit for unsupported certainty."],
        "quiz": [
            question("q1", "What is the first requirement before physical access in the applicable real workplace?",
                ["Review the authorized energy-isolation plan and verify isolation", "Compare the production counts",
                 "Read the maintenance budget", "Identify the asset purchase date", "Review the shift calendar"], 0,
                "The exercise begins with authorized safety planning and verified energy isolation. Follow the actual site procedure."),
            question("q2", "Which approach gives the strongest diagnostic conclusion?",
                ["Use the most recent alarm alone", "Select the most expensive component", "Correlate independent evidence and test alternatives",
                 "Select the most familiar fault name", "Use the oldest maintenance note alone"], 2,
                "Independent observations and plausible alternatives reduce unsupported diagnosis from a single symptom."),
            question("q3", "How should these sensor limits be applied?",
                ["Treat them as universal machine limits", "Use them to set a real machine controller", "Apply them to every component",
                 "Use them only within this synthetic training fixture", "Treat them as a manufacturer certification"], 3,
                "These are invented educational ranges. Real machinery requires approved limits for its exact configuration."),
        ]}
    manual_text = ("Original project-authored synthetic reference v1. " + machine["description"] + " "
        "All numeric values and observations are invented for this educational fixture and must not configure real equipment. "
        "Review authorized lockout/tagout and verification of stored-energy isolation before physical access. "
        "Use correlated observations and compare competing causes. " + explanation)
    pack = {"machine": machine, "sources": [
        {"id": f"{mid}.manual.v1", "kind": "manual", "title": f"{machine['name']} — synthetic reference", "locator": "Original project fixture / section 1",
         "content": {"text": manual_text}, "synthetic": True, "external_inference_allowed": True},
        {"id": f"{mid}.case.v1", "kind": "case", "title": observations["title"], "locator": "Original project fixture / case 1",
         "content": case, "synthetic": True, "external_inference_allowed": True}]}
    OUT.mkdir(exist_ok=True)
    (OUT / f"{mid}.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    """Write three synthetic machines and complete diagnostic fixtures; filesystem errors propagate."""
    mid = "cnc-v1"
    machine = {"id": mid, "name": "CNC machine", "description": "A simplified enclosed milling cell with a spindle, table and coolant loop.", "synthetic": True,
      "components": [component(mid, "base", "Machine bed", [0, .2, 0], [3, .4, 2], "#56606a"),
       component(mid, "column", "Column", [0, 1.5, -.65], [.8, 2.6, .65], "#bbc3c6"),
       component(mid, "spindle", "Spindle head", [0, 1.85, .05], [.8, .85, .8], "#e6e9e7",
                 sensor("vibration", "Spindle vibration", "mm/s", [0, 2.5], [[2.51, 8]])),
       component(mid, "tool", "Tool holder", [0, 1.25, .15], [.12, .4, .12], "#c3ec9e", shape="cylinder"),
       component(mid, "table", "Work table", [0, .7, .2], [2.1, .3, 1.3], "#8f9caa"),
       component(mid, "coolant", "Coolant unit", [1.8, .5, -.5], [.6, 1, .7], "#789d9d",
                 sensor("flow", "Coolant flow", "L/min", [6, 12], [[0, 5.99]]))]}
    write_pack(machine, [{"component_id": f"{mid}.spindle", "sensor_id": "vibration", "value": 4.2, "state": "abnormal"},
                         {"component_id": f"{mid}.coolant", "sensor_id": "flow", "value": 8, "state": "normal"}],
      {"title": "A change in surface finish", "briefing": "A milling cell develops a rough finish after a tooling change. Production is paused in the training record. Investigate the evidence before proposing a cause.",
       "evidence": [("Tooling record", "The recorded tool assembly has greater overhang than the stable comparison setup.", 2),
                    ("Controlled comparison", "In the archived virtual comparison, shorter overhang reduces vibration at the same simulated cutting conditions.", 5),
                    ("Coolant record", "Flow remains within the synthetic range; the recorded workpiece receives coolant.", 3),
                    ("Maintenance history", "No change in the recorded bearing trend preceded the tool change.", 4)]},
      ["Coolant restriction", "Excessive tool overhang", "Spindle bearing degradation", "Loose workholding", "Tool edge wear"], 1,
      "In this authored fixture, increased tool overhang and the controlled comparison support insufficient tooling stiffness. Vibration alone would not distinguish this from bearings or workholding.")
    mid = "press-v1"
    machine = {"id": mid, "name": "Hydraulic press", "description": "A simplified guarded press with a hydraulic power unit, reservoir and ram.", "synthetic": True,
      "components": [component(mid, "base", "Press bed", [0, .2, 0], [2.8, .4, 1.7], "#626a73"),
       component(mid, "left", "Left column", [-1.05, 1.6, 0], [.35, 2.8, .8], "#c4cccb"),
       component(mid, "right", "Right column", [1.05, 1.6, 0], [.35, 2.8, .8], "#c4cccb"),
       component(mid, "beam", "Crosshead", [0, 3, 0], [2.8, .4, 1], "#d8dddd"),
       component(mid, "ram", "Hydraulic ram", [0, 2.15, 0], [.35, 1.3, .35], "#b8d7c0",
                 sensor("pressure", "Circuit pressure", "bar", [70, 100], [[0, 69.99], [100.01, 120]]), "cylinder"),
       component(mid, "reservoir", "Reservoir", [1.9, .65, -.2], [.9, 1.3, 1.1], "#6d898d",
                 sensor("temperature", "Fluid temperature", "°C", [25, 55], [[55.01, 80]]))]}
    write_pack(machine, [{"component_id": f"{mid}.ram", "sensor_id": "pressure", "value": 48, "state": "abnormal"},
                         {"component_id": f"{mid}.reservoir", "sensor_id": "temperature", "value": 42, "state": "normal"}],
      {"title": "An inconsistent press cycle", "briefing": "A press has an inconsistent virtual cycle and noisy pressure response. Review the archived circuit observations and distinguish supply instability from other causes.",
       "evidence": [("Reservoir observation", "Recorded fluid imagery shows aeration during the affected cycle.", 2),
                    ("Supply comparison", "The archived comparison removes a simulated suction connection leak; aeration and pressure instability then disappear.", 5),
                    ("Temperature record", "Fluid temperature remains inside this training fixture's defined operating range.", 3),
                    ("Service history", "The symptom starts after a recorded suction-line service event.", 4)]},
      ["Ram seal leakage", "Cooling restriction", "Pressure-control drift", "Suction-side air ingress", "Directional valve restriction"], 3,
      "The authored aeration evidence and suction connection comparison support air ingress. Low pressure by itself could also arise from pressure control, pump delivery or internal leakage.")
    mid = "conveyor-v1"
    machine = {"id": mid, "name": "Conveyor belt", "description": "A simplified light-duty belt conveyor with drive, return pulley and support frame.", "synthetic": True,
      "components": [component(mid, "frame", "Support frame", [0, .55, 0], [3.8, .3, 1.3], "#9ca8ae"),
       component(mid, "belt", "Belt", [0, .8, 0], [3.6, .12, 1.2], "#3c5359",
                 sensor("speed", "Belt speed", "m/s", [.4, .6], [[0, .399]])),
       component(mid, "drive", "Drive unit", [-1.8, .6, .8], [.7, .55, .55], "#b6df9c",
                 sensor("current", "Drive current", "A", [1, 4], [[4.01, 8]]), "cylinder"),
       component(mid, "return", "Return pulley", [1.7, .7, 0], [.3, 1.2, .3], "#c2c8c9", shape="cylinder"),
       component(mid, "leg1", "Entry support", [-1.2, .1, 0], [.2, 1, 1], "#58616d"),
       component(mid, "leg2", "Exit support", [1.2, .1, 0], [.2, 1, 1], "#58616d")]}
    write_pack(machine, [{"component_id": f"{mid}.belt", "sensor_id": "speed", "value": .22, "state": "abnormal"},
                         {"component_id": f"{mid}.drive", "sensor_id": "current", "value": 3.2, "state": "normal"}],
      {"title": "Throughput below target", "briefing": "A conveyor moves more slowly under its simulated load even though the drive command is unchanged. Correlate motion, drive and service records.",
       "evidence": [("Motion comparison", "Archived marks show relative motion between the drive pulley surface and belt under the same virtual load.", 2),
                    ("Controlled verification", "A simulated restoration of the specified fixture tension eliminates the relative motion at unchanged load.", 5),
                    ("Drive record", "Current remains in the fixture's normal envelope; the virtual motor command has not changed.", 3),
                    ("Service history", "The symptom follows a recorded belt replacement, with no corresponding change in load.", 4)]},
      ["Insufficient belt traction", "Electrical overload", "Guide interference", "Excessive conveyed load", "Bearing seizure"], 0,
      "Relative motion and the controlled tension comparison support insufficient belt traction in this fixture. Slow speed alone cannot distinguish slip, overload or mechanical interference.")


if __name__ == "__main__":
    main()

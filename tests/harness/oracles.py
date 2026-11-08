"""Ground truth for scenarios, computed from the fixture with plain Python.

Each oracle takes the fixture's records ({resource: {id: record}}) and returns the set of ids a
correct answer must contain. Keeping them as code (not hand-copied ids) means a fixture rebuild
cannot silently invalidate a scenario.
"""


def _regions(records, acronym):
    return {i for i, r in records["anatomicalregion"].items() if r.get("acronym") == acronym}


def _species(records, name):
    return {i for i, r in records["species"].items() if r["name"] == name}


def ephys_sessions_in_ca1(records):
    """Sessions with an ExtracellularEphys acquisition that used an interface targeting CA1."""
    ca1 = _regions(records, "CA1")
    interfaces = {i for i, r in records["experimentalinterface"].items() if set(r["target_regions"]) & ca1}
    return {
        r["session"] for r in records["dataacquisition"].values()
        if r["type"] == "ExtracellularEphys" and set(r["interfaces"]) & interfaces
    }


def subjects_with_visp_virus_injection(records):
    visp = _regions(records, "VISp")
    return {
        r["subject"] for r in records["procedure"].values()
        if r["type"] == "VirusInjection" and set(r["target_regions"]) & visp
    }


def mice_without_silicon_probe(records):
    mice = {i for i, r in records["subject"].items() if r["species"] in _species(records, "Mus musculus")}
    implanted = {r["subject"] for r in records["procedure"].values() if r["type"] == "SiliconProbeImplant"}
    return mice - implanted


def rat_two_photon_sessions(records):
    rats = {i for i, r in records["subject"].items() if r["species"] in _species(records, "Rattus norvegicus")}
    sessions = {r["session"] for r in records["dataacquisition"].values() if r["type"] == "TwoPhotonMicroscopy"}
    return {s for s in sessions if set(records["session"][s]["subjects"]) & rats}


def sessions_with_probe_design(records, name="A1x32-6mm-50-177"):
    consumables = {i for i, r in records["consumable"].items() if r["name"] == name}
    stocks = {i for i, r in records["consumablestock"].items() if r.get("consumable") in consumables}
    interfaces = {
        r["experimental_interface"] for r in records["materialusage"].values()
        if r.get("experimental_interface") and (r.get("consumable") in consumables or r.get("consumable_stock") in stocks)
    }
    return {r["session"] for r in records["dataacquisition"].values() if set(r["interfaces"]) & interfaces}


def delayed_alternation_with_hippocampal_ephys(records):
    paradigms = {i for i, r in records["behavioralparadigm"].items() if r["name"] == "Delayed Alternation"}
    assays = {i for i, r in records["behavioralassay"].items() if r.get("behavioral_paradigm") in paradigms}
    behavior_sessions = {r["session"] for r in records["behavior"].values() if r["behavioralassay"] in assays}
    hippocampal = _regions(records, "CA1") | _regions(records, "CA3")
    interfaces = {i for i, r in records["experimentalinterface"].items() if set(r["target_regions"]) & hippocampal}
    ephys_sessions = {
        r["session"] for r in records["dataacquisition"].values()
        if r["type"] == "ExtracellularEphys" and set(r["interfaces"]) & interfaces
    }
    return behavior_sessions & ephys_sessions


def none(records):
    return set()

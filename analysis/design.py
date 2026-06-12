from dataclasses import dataclass, field

from analysis.capacity import CapacityResult, calculate_flexural_capacity
from models.materials import ConcreteProps, SteelProps
from models.section import SectionGeometry


NMM_PER_TONF_M = 9806650.0
N_PER_TONF = 9806.65


@dataclass
class CalculationStep:
    variable_name: str
    symbol: str
    formula: str
    substitution: str
    result: str
    unit: str
    reference: str
    explanation: str
    dependencies: list[str] = field(default_factory=list)


@dataclass
class CodeCheck:
    name: str
    reference: str
    description: str
    criterion: str
    status: str
    explanation: str


@dataclass
class DesignResult:
    Mu_tfm: float
    Vu_tf: float
    required_As: float
    provided_As: float
    phi_Mn_tfm: float
    phi_Vn_tf: float
    flexural_utilization: float
    shear_utilization: float
    utilization: float
    status: str
    capacity: CapacityResult
    calculation_steps: list[CalculationStep] = field(default_factory=list)
    code_checks: list[CodeCheck] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


def calculate_required_as(
    geom: SectionGeometry,
    target_mu_tfm: float,
    compression_as: float,
    d: float,
    dp: float,
    concrete: ConcreteProps,
    steel: SteelProps,
) -> float:
    """Find required tension steel area that reaches the target design moment."""
    target = abs(target_mu_tfm) * NMM_PER_TONF_M
    if target <= 0.0 or d <= dp:
        return 0.0

    lo = 0.0
    hi = max(100.0, 0.04 * geom.b * d)
    for _ in range(80):
        cap = calculate_flexural_capacity(geom, hi, compression_as, d, dp, concrete, steel)
        if cap.phi_Mn >= target:
            break
        hi *= 1.6
        if hi > 0.12 * geom.b * d:
            break

    for _ in range(80):
        mid = 0.5 * (lo + hi)
        cap = calculate_flexural_capacity(geom, mid, compression_as, d, dp, concrete, steel)
        if cap.phi_Mn >= target:
            hi = mid
        else:
            lo = mid
    return hi


def calculate_shear_strength(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    d: float,
    stirrup_spacing: float,
    stirrup_legs: int = 2,
) -> float:
    """Return phi*Vn in tonf using a compact ACI-style rectangular-beam model."""
    phi_v = 0.75
    vc = 0.17 * (concrete.fc_prime ** 0.5) * geom.b * d
    av = stirrup_legs * 3.141592653589793 * (geom.stirrup_dia / 2.0) ** 2
    spacing = max(stirrup_spacing, 1.0)
    vs = av * steel.fyt * d / spacing
    return phi_v * (vc + vs) / N_PER_TONF


def _format_num(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}"


def _build_calculation_steps(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    provided_as: float,
    compression_as: float,
    d: float,
    dp: float,
    mu_tfm: float,
    vu_tf: float,
    stirrup_spacing: float,
    required_as: float,
    phi_mn_tfm: float,
    phi_vn_tf: float,
    flex_util: float,
    shear_util: float,
    util: float,
    capacity: CapacityResult,
) -> list[CalculationStep]:
    phi_v = 0.75
    spacing = max(stirrup_spacing, 1.0)
    av = 2.0 * 3.141592653589793 * (geom.stirrup_dia / 2.0) ** 2
    vc = 0.17 * (concrete.fc_prime ** 0.5) * geom.b * d
    vs = av * steel.fyt * d / spacing
    vn = vc + vs
    y_comp = capacity.a / 2.0
    mu_nmm = abs(mu_tfm) * NMM_PER_TONF_M
    phi_mn_nmm = phi_mn_tfm * NMM_PER_TONF_M

    return [
        CalculationStep(
            "stress_block_factor",
            "beta1",
            "beta1 = 0.85 for f'c <= 28 MPa; otherwise reduced by 0.05 per 7 MPa, minimum 0.65",
            f"f'c = {_format_num(concrete.fc_prime, 2)} MPa",
            f"beta1 = {_format_num(concrete.beta1, 3)}",
            "-",
            "ACI 318-19 Sec. 22.2.2.4",
            "Defines the equivalent rectangular compression block depth used for flexural strength.",
            ["fc_prime"],
        ),
        CalculationStep(
            "neutral_axis_depth",
            "c",
            "force equilibrium: T - (Cc + Cs) = 0",
            f"{_format_num(capacity.T, 0)} - ({_format_num(capacity.Cc, 0)} + {_format_num(capacity.Cs, 0)}) = 0 N",
            f"c = {_format_num(capacity.c_na, 2)}",
            "mm",
            "ACI 318-19 Sec. 22.2.2 and Sec. 22.3",
            "Neutral axis depth is solved iteratively from internal force equilibrium.",
            ["As", "Asp", "fy", "fc_prime", "d", "dp", "beta1"],
        ),
        CalculationStep(
            "stress_block_depth",
            "a",
            "a = beta1 c",
            f"a = {_format_num(concrete.beta1, 3)} x {_format_num(capacity.c_na, 2)}",
            f"a = {_format_num(capacity.a, 2)}",
            "mm",
            "ACI 318-19 Sec. 22.2.2.4",
            "Equivalent rectangular compression block depth.",
            ["beta1", "c"],
        ),
        CalculationStep(
            "tensile_steel_force",
            "T",
            "T = As fst",
            f"T = {_format_num(provided_as, 2)} x min(Es eps_t, fy)",
            f"T = {_format_num(capacity.T, 0)}",
            "N",
            "ACI 318-19 Sec. 22.3",
            "Tension force in longitudinal reinforcement, limited by yield stress.",
            ["As", "Es", "eps_t", "fy"],
        ),
        CalculationStep(
            "concrete_compression_force",
            "Cc",
            "Cc = 0.85 f'c b a",
            f"Cc = 0.85 x {_format_num(concrete.fc_prime, 2)} x {_format_num(geom.b, 0)} x {_format_num(capacity.a, 2)}",
            f"Cc = {_format_num(capacity.Cc, 0)}",
            "N",
            "ACI 318-19 Sec. 22.2.2",
            "Compression force in the rectangular equivalent concrete stress block.",
            ["fc_prime", "b", "a"],
        ),
        CalculationStep(
            "compression_steel_force",
            "Cs",
            "Cs = As' (fsc - 0.85 f'c) when displaced concrete applies",
            f"Cs = {_format_num(compression_as, 2)} x net fsc",
            f"Cs = {_format_num(capacity.Cs, 0)}",
            "N",
            "ACI 318-19 Sec. 22.3",
            "Compression reinforcement contribution after accounting for concrete displaced by compression steel.",
            ["Asp", "fsc", "fc_prime"],
        ),
        CalculationStep(
            "nominal_moment_strength",
            "Mn",
            "Mn = Cc(d - a/2) + Cs(d - d')",
            f"Mn = {_format_num(capacity.Cc, 0)} x ({_format_num(d, 2)} - {_format_num(y_comp, 2)}) + {_format_num(capacity.Cs, 0)} x ({_format_num(d, 2)} - {_format_num(dp, 2)})",
            f"Mn = {_format_num(capacity.Mn / NMM_PER_TONF_M, 2)}",
            "tonf-m",
            "ACI 318-19 Sec. 22.3",
            "Nominal flexural strength about the tension steel centroid.",
            ["Cc", "Cs", "d", "a", "dp"],
        ),
        CalculationStep(
            "strength_reduction_factor",
            "phi",
            "phi = 0.90 if eps_t >= 0.005; phi = 0.65 if eps_t <= 0.002; interpolate otherwise",
            f"eps_t = {_format_num(capacity.eps_s, 5)}",
            f"phi = {_format_num(capacity.phi, 3)}",
            "-",
            "ACI 318-19 Table 21.2.2",
            "Strength reduction factor based on tensile strain condition.",
            ["eps_t"],
        ),
        CalculationStep(
            "design_moment_strength",
            "phiMn",
            "phiMn = phi Mn",
            f"phiMn = {_format_num(capacity.phi, 3)} x {_format_num(capacity.Mn / NMM_PER_TONF_M, 2)}",
            f"phiMn = {_format_num(phi_mn_tfm, 2)}",
            "tonf-m",
            "ACI 318-19 Sec. 21.2 and Sec. 22.3",
            "Design flexural strength compared with factored moment Mu.",
            ["phi", "Mn"],
        ),
        CalculationStep(
            "required_tensile_reinforcement",
            "As_required",
            "find As such that phiMn(As) >= Mu",
            f"target Mu = |{_format_num(mu_tfm, 2)}| x 9,806,650 = {_format_num(mu_nmm, 0)} N-mm",
            f"As_required = {_format_num(required_as, 2)}",
            "mm2",
            "ACI 318-19 Sec. 9.5 and Sec. 22.3",
            "Required steel is solved by bisection using the same flexural capacity equation shown above.",
            ["Mu", "phiMn", "fc_prime", "fy", "d", "dp"],
        ),
        CalculationStep(
            "provided_tensile_reinforcement",
            "As_provided",
            "As = sum(n pi db^2 / 4)",
            "As is summed from the active reinforcement table for the tension face.",
            f"As_provided = {_format_num(provided_as, 2)}",
            "mm2",
            "ACI 318-19 Sec. 20.2.1 and project bar schedule",
            "Provided tension reinforcement used in the flexural check.",
            ["bar_count", "bar_diameter"],
        ),
        CalculationStep(
            "concrete_shear_strength",
            "Vc",
            "Vc = 0.17 sqrt(f'c) b d",
            f"Vc = 0.17 x sqrt({_format_num(concrete.fc_prime, 2)}) x {_format_num(geom.b, 0)} x {_format_num(d, 2)}",
            f"Vc = {_format_num(vc / N_PER_TONF, 2)}",
            "tonf",
            "ACI 318-19 Table 22.5.5.1, simplified normalweight beam expression",
            "Concrete contribution used by the compact rectangular-beam shear model.",
            ["fc_prime", "b", "d"],
        ),
        CalculationStep(
            "stirrup_shear_strength",
            "Vs",
            "Vs = Av fyt d / s",
            f"Vs = {_format_num(av, 2)} x {_format_num(steel.fyt, 2)} x {_format_num(d, 2)} / {_format_num(spacing, 2)}",
            f"Vs = {_format_num(vs / N_PER_TONF, 2)}",
            "tonf",
            "ACI 318-19 Sec. 22.5.10.5",
            "Shear reinforcement contribution from two-leg stirrups.",
            ["Av", "fyt", "d", "s"],
        ),
        CalculationStep(
            "design_shear_strength",
            "phiVn",
            "phiVn = phi_v (Vc + Vs)",
            f"phiVn = {_format_num(phi_v, 2)} x ({_format_num(vc / N_PER_TONF, 2)} + {_format_num(vs / N_PER_TONF, 2)})",
            f"phiVn = {_format_num(phi_vn_tf, 2)}",
            "tonf",
            "ACI 318-19 Sec. 21.2 and Sec. 22.5",
            "Design shear strength compared with factored shear Vu.",
            ["phi_v", "Vc", "Vs"],
        ),
        CalculationStep(
            "flexural_utilization",
            "U_flex",
            "U_flex = |Mu| / phiMn",
            f"U_flex = |{_format_num(mu_tfm, 2)}| / {_format_num(phi_mn_tfm, 2)}",
            f"U_flex = {_format_num(flex_util, 3)}",
            "-",
            "ACI 318-19 Sec. 9.5",
            "Flexural demand-to-capacity ratio. Passing criterion is U_flex <= 1.0.",
            ["Mu", "phiMn"],
        ),
        CalculationStep(
            "shear_utilization",
            "U_shear",
            "U_shear = |Vu| / phiVn",
            f"U_shear = |{_format_num(vu_tf, 2)}| / {_format_num(phi_vn_tf, 2)}",
            f"U_shear = {_format_num(shear_util, 3)}",
            "-",
            "ACI 318-19 Sec. 9.5",
            "Shear demand-to-capacity ratio. Passing criterion is U_shear <= 1.0.",
            ["Vu", "phiVn"],
        ),
        CalculationStep(
            "governing_utilization",
            "U",
            "U = max(U_flex, U_shear)",
            f"U = max({_format_num(flex_util, 3)}, {_format_num(shear_util, 3)})",
            f"U = {_format_num(util, 3)}",
            "-",
            "ACI 318-19 Sec. 9.5",
            "Overall section status is PASS when the governing utilization is not greater than 1.0.",
            ["U_flex", "U_shear"],
        ),
    ]


def _build_code_checks(result: "DesignResult") -> list[CodeCheck]:
    return [
        CodeCheck(
            "Flexural Strength Check",
            "ACI 318-19 Sec. 9.5, Table 21.2.2, Sec. 22.3",
            "Required flexural strength must not exceed design flexural strength.",
            f"|Mu| <= phiMn -> {abs(result.Mu_tfm):.2f} <= {result.phi_Mn_tfm:.2f} tonf-m",
            "PASS" if result.flexural_utilization <= 1.0 else "FAIL",
            f"Flexural utilization = {result.flexural_utilization:.3f}.",
        ),
        CodeCheck(
            "Shear Strength Check",
            "ACI 318-19 Sec. 9.5, Sec. 21.2, Sec. 22.5",
            "Required shear strength must not exceed design shear strength.",
            f"|Vu| <= phiVn -> {abs(result.Vu_tf):.2f} <= {result.phi_Vn_tf:.2f} tonf",
            "PASS" if result.shear_utilization <= 1.0 else "FAIL",
            f"Shear utilization = {result.shear_utilization:.3f}.",
        ),
        CodeCheck(
            "Provided Reinforcement Check",
            "ACI 318-19 Sec. 9.6.1.2 and project detailing schedule",
            "Provided tension reinforcement is compared with calculated required reinforcement.",
            f"As_provided >= As_required -> {result.provided_As:.2f} >= {result.required_As:.2f} mm2",
            "PASS" if result.provided_As + 1e-9 >= result.required_As else "FAIL",
            "Minimum reinforcement code limits should be reviewed separately when preparing sealed calculations.",
        ),
    ]


def calculate_design_result(
    geom: SectionGeometry,
    concrete: ConcreteProps,
    steel: SteelProps,
    provided_as: float,
    compression_as: float,
    d: float,
    dp: float,
    mu_tfm: float,
    vu_tf: float,
    stirrup_spacing: float,
) -> DesignResult:
    capacity = calculate_flexural_capacity(geom, provided_as, compression_as, d, dp, concrete, steel)
    phi_mn_tfm = capacity.phi_Mn / NMM_PER_TONF_M
    phi_vn_tf = calculate_shear_strength(geom, concrete, steel, d, stirrup_spacing)
    required_as = calculate_required_as(geom, mu_tfm, compression_as, d, dp, concrete, steel)

    flex_util = abs(mu_tfm) / phi_mn_tfm if phi_mn_tfm > 0 else float("inf")
    shear_util = abs(vu_tf) / phi_vn_tf if phi_vn_tf > 0 else float("inf")
    util = max(flex_util, shear_util)
    result = DesignResult(
        Mu_tfm=mu_tfm,
        Vu_tf=vu_tf,
        required_As=required_as,
        provided_As=provided_as,
        phi_Mn_tfm=phi_mn_tfm,
        phi_Vn_tf=phi_vn_tf,
        flexural_utilization=flex_util,
        shear_utilization=shear_util,
        utilization=util,
        status="PASS" if util <= 1.0 else "FAIL",
        capacity=capacity,
    )
    result.calculation_steps = _build_calculation_steps(
        geom,
        concrete,
        steel,
        provided_as,
        compression_as,
        d,
        dp,
        mu_tfm,
        vu_tf,
        stirrup_spacing,
        required_as,
        phi_mn_tfm,
        phi_vn_tf,
        flex_util,
        shear_util,
        util,
        capacity,
    )
    result.assumptions = [
        "Rectangular reinforced concrete beam section.",
        "Normalweight concrete with lambda = 1.0.",
        "Plane sections remain plane; concrete ultimate strain eps_cu = 0.003.",
        "Flexural strength uses the ACI equivalent rectangular stress block.",
        "Shear strength uses a compact nonprestressed beam model: Vc = 0.17 sqrt(f'c) b d and Vs = Av fyt d / s.",
        "Two-leg stirrups are assumed for shear reinforcement.",
        "Loads are factored design actions entered by the user.",
    ]
    result.code_checks = _build_code_checks(result)
    return result

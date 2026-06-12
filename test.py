"""
ACI 318 Flexural Capacity - Standalone Test
Units: ksc (stress), tonf (force), tonf.m (moment), mm (length)
"""
import math

# --- Unit conversion constants -----------------------------------------------
KSC_TO_MPA   = 0.0980665      # 1 ksc = 0.0980665 N/mm2
NMM_TO_TONFM = 1 / 9_806_650  # 1 N.mm = 1/9,806,650 tonf.m
N_TO_TONF    = 1 / 9_806.65   # 1 N    = 1/9,806.65  tonf

# --- Material & section parameters -------------------------------------------
b       = 400    # mm  - beam width
h       = 600    # mm  - total depth
d       = 550    # mm  - effective depth to tension steel centroid
d_prime = 60     # mm  - depth to compression steel centroid

# Steel areas in cm2  (will convert to mm2 for force calculations)
As_bot_cm2 = (math.pi * 2**2 / 4) * 4   # 4 x DB20  (tension / bottom)
As_top_cm2 = (math.pi * 2**2 / 4) * 2   # 2 x DB20  (compression / top)

fc_ksc = 280        # ksc
fy_ksc = 4000       # ksc
Es_ksc = 2_000_000  # ksc  (~200,000 MPa)
eps_cu = 0.003      # max concrete compressive strain

# --- Derived values -----------------------------------------------------------
fc_mpa = fc_ksc * KSC_TO_MPA
fy_mpa = fy_ksc * KSC_TO_MPA
Es_mpa = Es_ksc * KSC_TO_MPA  # ~196,133 MPa (close to 200,000 MPa)

As_bot = As_bot_cm2 * 100  # cm2 -> mm2
As_top = As_top_cm2 * 100  # cm2 -> mm2


# --- beta1  (ACI 318-19 Sec 22.2.2.4, thresholds in ksc) --------------------
def beta1(fc):
    """Stress-block factor.  fc in ksc."""
    if fc <= 280:
        return 0.85
    elif fc <= 550:
        return 0.85 - 0.05 * (fc - 280) / 70
    else:
        return 0.65


# --- Force equilibrium  (forces in N, lengths in mm) -------------------------
def force_balance(c):
    """Return T - C  [N].  c = neutral-axis depth from compression face [mm]."""
    b1 = beta1(fc_ksc)
    a  = b1 * c

    eps_t = eps_cu * (d       - c) / c
    eps_c = eps_cu * (c - d_prime) / c   # negative when c < d_prime

    fst = min(Es_mpa * eps_t,  fy_mpa)
    fsc = min(max(Es_mpa * eps_c, -fy_mpa), fy_mpa)

    T  = As_bot * fst
    Cc = 0.85 * fc_mpa * b * a
    Cs = As_top * fsc
    return T - (Cc + Cs)


def dF(c, h=1e-3):
    return (force_balance(c + h) - force_balance(c - h)) / (2 * h)


# --- Newton-Raphson solver ----------------------------------------------------
def find_c(c0=100.0, tol=1e-4, max_iter=60):
    c = c0
    for i in range(max_iter):
        F  = force_balance(c)
        if abs(F) < tol:
            break
        dFv = dF(c)
        if abs(dFv) < 1e-12:
            break
        c -= F / dFv
        if c <= d_prime:
            c = d_prime + 1.0
        if c >= d:
            c = d - 1.0
    return c, i + 1


# --- Solve -------------------------------------------------------------------
c_na, n_iter = find_c()

b1  = beta1(fc_ksc)
a   = b1 * c_na

eps_t = eps_cu * (d       - c_na) / c_na
eps_c = eps_cu * (c_na - d_prime) / c_na

fst_mpa = min(Es_mpa * eps_t,  fy_mpa)
fsc_mpa = min(max(Es_mpa * eps_c, -fy_mpa), fy_mpa)
fst_ksc = fst_mpa / KSC_TO_MPA
fsc_ksc = fsc_mpa / KSC_TO_MPA

T_N  = As_bot * fst_mpa
Cc_N = 0.85 * fc_mpa * b * a
Cs_N = As_top * fsc_mpa
C_N  = Cc_N + Cs_N

# --- phi factor  (ACI 318-19 Sec 21.2.2) ------------------------------------
if eps_t >= 0.005:
    phi = 0.90
elif eps_t <= 0.002:
    phi = 0.65
else:
    phi = 0.65 + (eps_t - 0.002) * (250.0 / 3.0)

# --- Moment capacity (N.mm -> tonf.m) ----------------------------------------
# Cc acts at a/2 from compression face; Cs acts at d'; T acts at d
Mn_Nmm    = Cc_N * (d - a / 2) + Cs_N * (d - d_prime)

Mn = ((T_N-Cs_N)*(d-a/2)) + Cs_N*(d-d_prime)  # alternative calculation of Mn, should give same result as above

phiMn_Nmm = phi * Mn_Nmm

Mn_tonfm    = Mn_Nmm    * NMM_TO_TONFM
phiMn_tonfm = phiMn_Nmm * NMM_TO_TONFM

T_tonf  = T_N  * N_TO_TONF
C_tonf  = C_N  * N_TO_TONF
err_pct = abs(T_N - C_N) / max(T_N, 1) * 100

# --- Report ------------------------------------------------------------------
sep  = "=" * 60
sep2 = "-" * 60

print(sep)
print("  ACI 318 Flexural Capacity  -  MKS Units")
print(sep)

print("\n[INPUT]")
print(f"  b          = {b} mm")
print(f"  h          = {h} mm")
print(f"  d          = {d} mm        (tension steel centroid from comp. face)")
print(f"  d'         = {d_prime} mm        (compression steel centroid from comp. face)")
n_bot = int(round(As_bot_cm2 / (math.pi * 2.0**2 / 4)))
n_top = int(round(As_top_cm2 / (math.pi * 2.0**2 / 4)))
print(f"  As,bot     = {As_bot_cm2:.3f} cm2 -> {As_bot:.1f} mm2  ({n_bot}x DB20, tension)")
print(f"  As,top     = {As_top_cm2:.3f} cm2 -> {As_top:.1f} mm2  ({n_top}x DB20, compression)")
print(f"  f'c        = {fc_ksc} ksc  ({fc_mpa:.2f} MPa)")
print(f"  fy         = {fy_ksc} ksc  ({fy_mpa:.2f} MPa)")
print(f"  Es         = {Es_ksc:,} ksc  ({Es_mpa:.0f} MPa)")

print(f"\n[GEOMETRY]")
print(f"  beta1      = {b1:.4f}")
print(f"  c  (NA)    = {c_na:.2f} mm   (Newton-Raphson, {n_iter} iterations)")
print(f"  a  (block) = {a:.2f} mm   (= beta1 x c)")
print(f"  a/d        = {a/d:.4f}")
print(f"  c/d        = {c_na/d:.4f}")

print(f"\n[STRAINS]")
print(f"  eps_cu     = {eps_cu:.4f}   (assumed max compressive strain)")
print(f"  eps_t      = {eps_t:.4f}   (tension steel)")
print(f"  eps_c      = {eps_c:.4f}   (compression steel)")
print(f"  eps_y      = {fy_mpa/Es_mpa:.4f}   (yield strain = fy/Es)")

print(f"\n[STRESSES]")
print(f"  0.85*f'c   = {0.85*fc_ksc:>9.1f} ksc  ({0.85*fc_mpa:.2f} MPa)  (stress block intensity)")
print(f"  fst (tens) = {fst_ksc:>9.1f} ksc  ({fst_mpa:.2f} MPa)  {'<-- YIELDED' if fst_mpa >= fy_mpa - 0.01 else '(elastic)'}")
print(f"  fsc (comp) = {fsc_ksc:>9.1f} ksc  ({fsc_mpa:.2f} MPa)  {'<-- YIELDED' if abs(fsc_mpa) >= fy_mpa - 0.01 else '(elastic)'}")

print(f"\n[FORCES]")
print(f"  T   (tension)     = {T_tonf:>9.3f} tonf  (= {T_N/1000:.2f} kN)")
print(f"  Cc  (conc. block) = {Cc_N*N_TO_TONF:>9.3f} tonf  (= {Cc_N/1000:.2f} kN)")
print(f"  Cs  (comp. steel) = {Cs_N*N_TO_TONF:>9.3f} tonf  (= {Cs_N/1000:.2f} kN)")
print(f"  C   (total comp.) = {C_tonf:>9.3f} tonf  (= {C_N/1000:.2f} kN)")
print(sep2)
print(f"  |T - C| / T       = {err_pct:.6f} %  (equilibrium error)")

print(f"\n[PHI FACTOR  (ACI 318-19 Sec 21.2.2)]")
if eps_t >= 0.005:
    ctrl = "TENSION-CONTROLLED"
elif eps_t <= 0.002:
    ctrl = "COMPRESSION-CONTROLLED"
else:
    ctrl = "TRANSITION ZONE"
print(f"  eps_t = {eps_t:.4f}  -->  {ctrl}")
print(f"  phi   = {phi:.4f}")

Mn_alt = ((T_N - Cs_N) * (d - a/2)) + Cs_N * (d - d_prime)

print(f"\n[MOMENT CAPACITY]")
print(f"  Method A  :  Mn = Cc*(d-a/2) + Cs*(d-d')")
print(f"    Mn  (A)  = {Mn_Nmm*NMM_TO_TONFM:>9.3f} tonf.m")
print(f"  Method B  :  Mn = (T-Cs)*(d-a/2) + Cs*(d-d')   [Cc = T-Cs by equilibrium]")
print(f"    Mn  (B)  = {Mn_alt*NMM_TO_TONFM:>9.3f} tonf.m")
print(f"  Difference = {abs(Mn_Nmm - Mn_alt):.6f} N.mm  ({abs(Mn_Nmm - Mn_alt)*NMM_TO_TONFM:.8f} tonf.m)")
print(sep2)
print(f"  Mn         = {Mn_tonfm:>9.3f} tonf.m  (= {Mn_Nmm/1e6:.3f} kN.m)")
print(f"  phi.Mn     = {phiMn_tonfm:>9.3f} tonf.m  (= {phiMn_Nmm/1e6:.3f} kN.m)")

print(f"\n[STEEL RATIO CHECK]")
rho     = As_bot / (b * d)
rho_b   = (0.85 * b1 * fc_mpa / fy_mpa) * (600 / (600 + fy_mpa))
rho_max = 0.75 * rho_b
rho_min = max(0.25 * math.sqrt(fc_mpa) / fy_mpa, 1.4 / fy_mpa)
print(f"  rho        = {rho:.5f}  ({rho*100:.3f} %)")
print(f"  rho_min    = {rho_min:.5f}  ({rho_min*100:.3f} %)  (ACI 318 min)")
print(f"  rho_bal    = {rho_b:.5f}  ({rho_b*100:.3f} %)")
print(f"  rho_max    = {rho_max:.5f}  ({rho_max*100:.3f} %)  (0.75 x rho_bal)")
print(f"  rho_min < rho < rho_max ? {'YES -- OK' if rho_min < rho < rho_max else 'FAIL -- check reinforcement'}")
print(sep)

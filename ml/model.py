"""Modelo predictivo de CacaoResiliente (Fase 4).

Predice la anomalía de producción de cacao  y = 100·(R − T)/T  de un área y un año a
partir del clima de la época lluviosa (ene–jun).

    z_k      = (x_k − μ_{a,k}) / σ_{a,k}            anomalía climática estandarizada del área a
                                                     (μ, σ = normal climática 1991–2020 del área)
    Ridge:   ŷ = β₀ + Σ_k β_k·s(z_k) + γ·s(max(0, z_lluvia − c))     c = 2 desviaciones
             β̂ = argmin Σ_i w_i (y_i − ŷ_i)² + λ‖β‖²   sujeto a signo(β_k) = signo físico
             (λ por validación cruzada interna)
    Pesos    w_i ∝ 1/s_a²    (s_a = desviación del target en el área: las provincias con
                              estadísticas más ruidosas pesan menos)
    Intervalo [p10, p90] = ŷ + s_a·[q_0.1, q_0.9]   (q = cuantiles de los residuos fuera de
                              muestra r_i/s_a de la validación leave-one-year-out, por nivel)
    Pérdida  = min(100, max(0, −ŷ))  %

El modelo NO extrapola: cada término se recorta al rango visto en el entrenamiento (un clima
más extremo que el peor año observado devuelve la pérdida de ese peor año y `extrapolated=True`).

`QuantileGBR` y `Ensemble` (gradient boosting cuantílico y su mezcla con el Ridge) se
entrenan solo como comparación: con ~200 filas no mejoran al Ridge (ver `ml.train`).

Todos los objetos tienen `fit(X, y)` / `predict(X)` donde X es un DataFrame con las columnas
`area_name`, `year` y las features crudas del panel; así sirven tal cual en `validation.loyo`
y en la API.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .features import REF_PERIOD

ID_COLS = ["area_name", "year"]
QUANTILES = (0.1, 0.5, 0.9)
ALPHAS = np.logspace(-1, 3, 25)
MIN_NORMAL_YEARS = 10       # años mínimos de historial para la normal climática de un área

# Áreas que no se usan para entrenar (decidido en la Fase 2, antes de ver resultados del
# modelo): Sucumbíos es Amazonía (otro régimen de lluvia, sin señal de El Niño costero), la
# corrección de lluvia ERA5→GPM es mala allí (r = 0.38) y su serie de rendimiento es ruido
# de muestreo (sd 57 %, autocorrelación −0.82).
EXCLUDE_AREAS = ["Sucumbios"]


@dataclass(frozen=True)
class FeatureSpec:
    """Qué columnas entran al modelo y cómo se transforman."""
    anom: tuple[str, ...]                       # → anomalía estandarizada del área (z)
    raw: tuple[str, ...] = ()                   # → tal cual
    hinges: tuple[tuple[str, float], ...] = ()  # (columna, umbral) → max(0, t − umbral), solo Ridge;
    #                                             t = z si la columna está en `anom`, x si en `raw`
    signs: tuple[tuple[str, int], ...] = ()     # signo físico esperado del efecto (−1 daña, +1 ayuda)
    fill_zero: tuple[str, ...] = ()             # sin dato → anomalía 0 (= año normal), p. ej. MODIS antes de 2000

    @property
    def inputs(self) -> list[str]:
        return list(dict.fromkeys([*self.anom, *self.raw, *(c for c, _ in self.hinges)]))

    @property
    def columns(self) -> list[str]:
        return ID_COLS + self.inputs

    def sign(self, col: str) -> int:
        """Signo impuesto al efecto de `col` (0 = libre). Un umbral hereda el de su variable."""
        d = dict(self.signs)
        for c, k in self.hinges:
            d.setdefault(hinge_name(c, k), d.get(c, 0))
        return d.get(col, 0)


# Conjunto principal: pocas variables, una por mecanismo, todas de la época lluviosa (ene–jun)
# y cada una con el signo que dicta la fitopatología: más humedad / lluvia → más moniliasis y
# mazorca negra → menos cacao; más sol → menos enfermedad.
#   · La lluvia y su umbral van en desviaciones estándar DEL ÁREA (no en %): en zonas secas
#     (El Oro, Guayas) un +100 % de lluvia es frecuente y no es un evento extremo.
#     Umbral c = 2 σ ≈ +60 % de lluvia a escala nacional.
#   · La temperatura media NO entra como término lineal: su efecto llega por la ventana térmica
#     de los días favorables (20–30 °C).
#   · El índice Niño 1+2 NO entra: una vez conocida la lluvia local no aporta nada (su
#     coeficiente es 0 en la validación). El Niño actúa a través de la lluvia.
CLIMATE_CORE = FeatureSpec(
    anom=("saturated_days", "fav_days_phytophthora", "solar_mean", "rain_total"),
    hinges=(("rain_total", 2.0),),
    signs=(("saturated_days", -1), ("fav_days_phytophthora", -1), ("solar_mean", 1),
           ("rain_total", -1)),
)

# + verdor de la vegetación medido por satélite (MODIS EVI, ene–jun): medida objetiva del estado
# del cultivo en cada provincia, independiente de la encuesta ESPAC. Solo existe desde 2000: sin
# dato (años anteriores, escenarios 2050) se toma anomalía 0 = verdor normal.
CORE = FeatureSpec(
    anom=CLIMATE_CORE.anom + ("evi_jan_jun",),
    hinges=CLIMATE_CORE.hinges,
    signs=CLIMATE_CORE.signs + (("evi_jan_jun", 1),),
    fill_zero=("evi_jan_jun",),
)

# Grupos para explicar el resultado (las variables de humedad están muy correlacionadas:
# el reparto entre ellas no es estable, la suma del grupo sí).
FACTOR_GROUPS = {
    "exceso_de_lluvia": ["rain_total", "rain_anom_pct", "rain_max_1d", "rain_max_5d", "wet_days",
                         "max_wet_spell", "heavy_rain_days", "rain_p95_days", "water_balance"],
    "suelo_saturado": ["saturated_days"],
    "dias_favorables_enfermedad": ["fav_days_phytophthora", "fav_days_monilia", "rh_mean"],
    "temperatura": ["t_mean", "tmax_mean", "tmin_mean"],
    "radiacion_solar": ["solar_mean", "et0_total"],
    "verdor_satelite": ["evi_jan_jun"],
    "el_nino_oceano": ["nino12_jan_jun", "oni_jan_jun", "nino34_jan_jun", "oni_djf"],
}
GROUP_OF = {f: g for g, fs in FACTOR_GROUPS.items() for f in fs}


def hinge_name(col: str, knot: float) -> str:
    return f"{col}_gt{knot:g}"


def area_weights(area: pd.Series, y: pd.Series, scale: dict | None = None) -> tuple[np.ndarray, dict]:
    """Pesos 1/s_a² (media 1) y la escala de ruido s_a de cada área."""
    if scale is None:
        s = y.groupby(area.to_numpy()).std()
        scale = s.fillna(s.median()).to_dict()          # área con una sola fila → escala mediana
    s = area.map(scale).to_numpy(float)
    w = 1.0 / s ** 2
    return w / w.mean(), scale


# ══════════════════════════════════════════════════════════════════════════════════════
class Preprocessor:
    """Features crudas → matriz del modelo (anomalías estandarizadas por área + umbrales).

    `climate`: tabla área × año con las features climáticas de todos los años. Si se da, la
    normal de cada área se calcula sobre 1991–2020 usando solo los años presentes en el
    entrenamiento (en validación cruzada el año de test no participa ni en su propia normal).
    Si no se da, la normal sale de las filas de entrenamiento.

    Cada término se recorta al rango [mín, máx] visto en el entrenamiento: el modelo no
    extrapola más allá del clima más extremo con el que se ajustó.
    """

    def __init__(self, spec: FeatureSpec = CORE, climate: pd.DataFrame | None = None,
                 ref_period: tuple[int, int] = REF_PERIOD):
        self.spec, self.climate, self.ref_period = spec, climate, ref_period

    def fit(self, X: pd.DataFrame) -> "Preprocessor":
        anom = list(self.spec.anom)
        if self.climate is not None:
            ref = self.climate[self.climate.year.between(*self.ref_period)
                               & self.climate.year.isin(X.year.unique())]
        else:
            ref = X
        g = ref.groupby("area_name")[anom]
        self.mean_, self.sd_ = g.mean(), g.std().replace(0, np.nan)
        self.sd_ = self.sd_.fillna(self.sd_.median())
        t = self._terms(X)
        self.lo_, self.hi_ = t.min(), t.max()
        return self

    def add_area(self, name: str, climate: pd.DataFrame) -> None:
        """Registra un área nueva (cantón, polígono) a partir de su historial de features."""
        ref = climate[climate.year.between(*self.ref_period)][list(self.spec.anom)].dropna()
        if len(ref) < MIN_NORMAL_YEARS:
            raise ValueError(f"{name}: hacen falta ≥ {MIN_NORMAL_YEARS} años de "
                             f"{self.ref_period[0]}–{self.ref_period[1]} para la normal climática")
        sd = ref.std().replace(0, np.nan)
        self.mean_.loc[name], self.sd_.loc[name] = ref.mean(), sd.fillna(self.sd_.median())

    def _terms(self, X: pd.DataFrame) -> pd.DataFrame:
        missing = set(X.area_name) - set(self.mean_.index)
        if missing:
            raise KeyError(f"Áreas sin normal climática: {sorted(missing)} (usa add_area)")
        anom = list(self.spec.anom)
        out = pd.DataFrame(index=X.index)
        mu = self.mean_.reindex(X.area_name).to_numpy()
        sd = self.sd_.reindex(X.area_name).to_numpy()
        out[anom] = (X[anom].to_numpy(float) - mu) / sd
        for c in self.spec.fill_zero:
            if c in out:
                out[c] = out[c].fillna(0.0)
        for c in self.spec.raw:
            out[c] = X[c].to_numpy(float)
        for c, k in self.spec.hinges:
            out[hinge_name(c, k)] = np.clip(out[c].to_numpy(float) - k, 0, None)
        return out

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return self._terms(X).clip(self.lo_, self.hi_, axis=1)

    def extrapolated(self, X: pd.DataFrame) -> np.ndarray:
        """True si algún término cae fuera del rango de entrenamiento (se recortó)."""
        t = self._terms(X)
        return ((t < self.lo_ - 1e-9) | (t > self.hi_ + 1e-9)).any(axis=1).to_numpy()

    # el objeto guardado no necesita la tabla climática completa
    def __getstate__(self):
        return {**self.__dict__, "climate": None}


# ══════════════════════════════════════════════════════════════════════════════════════
class _Base:
    """Preprocesado + pesos por área comunes a todos los modelos."""

    def __init__(self, spec: FeatureSpec = CORE, climate: pd.DataFrame | None = None,
                 weighted: bool = True):
        self.spec, self.climate, self.weighted = spec, climate, weighted

    def _prepare(self, X: pd.DataFrame, y: pd.Series):
        self.pre_ = Preprocessor(self.spec, self.climate).fit(X)
        w, self.scale_ = area_weights(X.area_name, y)
        return self.pre_.transform(X), (w if self.weighted else np.ones(len(X)))

    def __getstate__(self):
        return {**self.__dict__, "climate": None}


class RidgeModel(_Base):
    """ŷ = β₀ + Σ β_k·s(z_k), con signo(β_k) fijado por la física cuando `spec.signs` lo indica.

    λ se elige por validación cruzada interna (GCV de RidgeCV) y con ese λ se resuelve el
    problema con restricción de signo (mínimos cuadrados no negativos sobre ±s(z_k)).
    Con variables de humedad muy correlacionadas, sin restricción los coeficientes cambian
    de signo para compensarse entre sí; con ella cada término se puede leer por separado.
    """

    def __init__(self, spec=CORE, climate=None, weighted=True, constrained=True):
        super().__init__(spec, climate, weighted)
        self.constrained = constrained

    def fit(self, X, y):
        Z, w = self._prepare(X, y)
        self.cols_ = list(Z.columns)
        self.scaler_ = StandardScaler().fit(Z)
        S = self.scaler_.transform(Z)
        cv = RidgeCV(alphas=ALPHAS).fit(S, y, sample_weight=w)
        self.alpha_ = float(cv.alpha_)
        sg = np.array([self.spec.sign(c) for c in self.cols_])
        if not self.constrained or not sg.any():
            self.coef_, self.intercept_ = cv.coef_, float(cv.intercept_)
            return self
        free = sg == 0                               # libres: entran como +x y −x
        A = np.hstack([S * np.where(free, 1, sg), -S[:, free]])
        nn = Ridge(alpha=self.alpha_, positive=True, tol=1e-10).fit(A, y, sample_weight=w)
        b = nn.coef_[:len(sg)] * np.where(free, 1, sg)
        b[free] -= nn.coef_[len(sg):]
        self.coef_, self.intercept_ = b, float(nn.intercept_)
        return self

    def _s(self, X):
        return self.scaler_.transform(self.pre_.transform(X)[self.cols_])

    def predict(self, X):
        return self.intercept_ + self._s(X) @ self.coef_

    def coefficients(self) -> pd.Series:
        """β por desviación estándar de cada término (puntos % de producción)."""
        return pd.Series(self.coef_, index=self.cols_)

    def contributions(self, X) -> pd.DataFrame:
        """c_k = β_k·s(z_k): cuánto mueve cada feature la predicción respecto a un año medio."""
        c = pd.DataFrame(self._s(X) * self.coef_, columns=self.cols_, index=X.index)
        for col, k in self.spec.hinges:                      # el umbral es parte de su variable
            c[col] = c.get(col, 0) + c.pop(hinge_name(col, k))
        return c


class QuantileGBR(_Base):
    """Gradient boosting cuantílico: árboles poco profundos, pérdida pinball, p10/p50/p90.

    Solo para comparar con el Ridge. `monotone=True` pasa el signo físico de `spec.signs` como
    restricción a cada árbol; con pérdida cuantílica scikit-learn NO garantiza que la
    predicción final sea monótona (los valores de las hojas se reajustan), solo la favorece.
    """

    def __init__(self, spec=CORE, climate=None, weighted=True, monotone=True, n_estimators=150,
                 max_depth=2, learning_rate=0.05, min_samples_leaf=10):
        super().__init__(spec, climate, weighted)
        self.monotone = monotone
        self.params = dict(max_iter=n_estimators, max_depth=max_depth, learning_rate=learning_rate,
                           min_samples_leaf=min_samples_leaf, early_stopping=False, random_state=0)

    def fit(self, X, y):
        Z, w = self._prepare(X, y)
        self.cols_ = [c for c in Z.columns if c in self.spec.inputs]     # sin columnas de umbral
        cst = [self.spec.sign(c) if self.monotone else 0 for c in self.cols_]
        with threadpool_limits(limits=1):            # ~200 filas: varios hilos solo estorban
            self.models_ = {q: HistGradientBoostingRegressor(loss="quantile", quantile=q,
                                                             monotonic_cst=cst, **self.params)
                            .fit(Z[self.cols_], y, sample_weight=w) for q in QUANTILES}
        return self

    def _z(self, X):
        return self.pre_.transform(X)[self.cols_]

    def predict(self, X):
        with threadpool_limits(limits=1):
            return self.models_[0.5].predict(self._z(X))

    def predict_quantiles(self, X):
        Z = self._z(X)
        with threadpool_limits(limits=1):
            lo, mid, hi = (self.models_[q].predict(Z) for q in QUANTILES)
        return np.minimum(lo, mid), mid, np.maximum(hi, mid)

    def contributions(self, X) -> pd.DataFrame:
        """Valores SHAP (TreeExplainer) del modelo de la mediana."""
        import shap
        Z = self._z(X)
        sv = shap.TreeExplainer(self.models_[0.5]).shap_values(Z)
        return pd.DataFrame(sv, columns=self.cols_, index=X.index)


class Ensemble(_Base):
    """ŷ = w·Ridge + (1 − w)·GBR_p50 (comparación; el modelo final usa w = 1, solo Ridge)."""

    def __init__(self, spec=CORE, climate=None, weighted=True, w: float = 0.5,
                 constrained: bool = True, **gbr_kw):
        super().__init__(spec, climate, weighted)
        self.w, self.constrained, self.gbr_kw = w, constrained, gbr_kw

    def fit(self, X, y):
        self.ridge_ = RidgeModel(self.spec, self.climate, self.weighted, self.constrained).fit(X, y)
        self.gbr_ = QuantileGBR(self.spec, self.climate, self.weighted, **self.gbr_kw).fit(X, y)
        self.gbr_.pre_ = self.ridge_.pre_            # un solo preprocesador (add_area vale para ambos)
        self.pre_, self.scale_ = self.ridge_.pre_, self.ridge_.scale_
        return self

    def parts(self, X) -> tuple[np.ndarray, np.ndarray]:
        return self.ridge_.predict(X), self.gbr_.predict(X)

    def predict(self, X):
        r, g = self.parts(X)
        return self.w * r + (1 - self.w) * g

    def predict_quantiles(self, X):
        lo, mid, hi = self.gbr_.predict_quantiles(X)
        p = self.predict(X)
        return p + (lo - mid), p, p + (hi - mid)

    def contributions(self, X) -> pd.DataFrame:
        if self.w == 1:
            return self.ridge_.contributions(X)
        cg = self.gbr_.contributions(X)
        if self.w == 0:
            return cg
        return self.w * self.ridge_.contributions(X).reindex(columns=cg.columns, fill_value=0) + (1 - self.w) * cg


# ══════════════════════════════════════════════════════════════════════════════════════
def risk_class(loss_pct: float) -> str:
    return "bajo" if loss_pct < 5 else "medio" if loss_pct < 15 else "alto" if loss_pct < 30 else "muy_alto"


NATIONAL = "national"


@dataclass
class CacaoLossModel:
    """Lo que se guarda en `cacao_loss_vX.joblib` y carga la API.

    model          RidgeModel ajustado con todos los datos
    resid_q        {"national": (q10, q90), "province": (q10, q90)}: cuantiles de los residuos
                   LOYO normalizados r/s_a (intervalo conformal), por nivel
    noise_scale    s_a por área; `default_scale` para áreas nuevas (cantones, polígonos)
    """
    model: RidgeModel
    resid_q: dict
    noise_scale: dict
    default_scale: float
    version: str = "v1"
    meta: dict = field(default_factory=dict)

    @property
    def features(self) -> list[str]:
        return self.model.spec.inputs

    def predict(self, X: pd.DataFrame, top: int = 3) -> pd.DataFrame:
        """X: area_name, year + features crudas. Devuelve una fila por fila de X."""
        X = X.reset_index(drop=True)
        y = self.model.predict(X)
        nat = (X.area_name == NATIONAL).to_numpy()
        s = X.area_name.map(self.noise_scale).fillna(self.default_scale).to_numpy(float)
        q = np.array([self.resid_q["national" if n else "province"] for n in nat])
        p10, p90 = y + s * q[:, 0], y + s * q[:, 1]
        out = X[ID_COLS].copy()
        out["y_anom_pct"] = y
        out["y_anom_p10"], out["y_anom_p90"] = p10, p90
        # pérdida = −anomalía (entre 0 y 100 %); el p10 de la anomalía es el p90 de la pérdida
        out["loss_pct"] = np.clip(-y, 0, 100)
        out["loss_p10"], out["loss_p90"] = np.clip(-p90, 0, 100), np.clip(-p10, 0, 100)
        out["risk_class"] = [risk_class(v) for v in out.loss_pct]
        factors = self.explain(X)
        out["top_factors"] = [
            [{"name": k, "contribution": round(float(v), 2)}
             for k, v in row.reindex(row.abs().sort_values(ascending=False).index).head(top).items()]
            for _, row in factors.iterrows()]
        # clima más extremo que cualquier año de entrenamiento: la pérdida real puede ser mayor
        out["extrapolated"] = self.model.pre_.extrapolated(X)
        # la respuesta se validó con la serie nacional; por zona es un índice sin validar
        out["evidence"] = np.where(nat, "validado_nacional", "indice_subnacional_no_validado")
        out["model_version"] = self.version
        return out

    def explain(self, X: pd.DataFrame) -> pd.DataFrame:
        """Contribución (puntos % de producción) de cada grupo de factores. Negativo = pérdida."""
        c = self.model.contributions(X)
        return c.T.groupby(lambda f: GROUP_OF.get(f, f)).sum().T

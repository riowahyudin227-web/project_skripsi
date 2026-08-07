import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st


# =========================================================
# KONFIGURASI PATH DAN KOLOM
# =========================================================
BASE_DIR = Path(__file__).resolve().parent

# Utamakan file yang berada satu folder dengan app.py (struktur GitHub).
# Jika tidak ada, gunakan struktur folder lama sebagai cadangan.
USERS_PATH = (
    BASE_DIR / "users.json"
    if (BASE_DIR / "users.json").exists()
    else BASE_DIR / "config" / "users.json"
)

DATA_PATH = (
    BASE_DIR / "penerima.csv"
    if (BASE_DIR / "penerima.csv").exists()
    else BASE_DIR / "data" / "penerima.csv"
)

PKH_COLUMNS = ["AUD", "SD", "SMP", "SMA", "DB", "LU", "HAMIL", "HAM"]
AHP_THRESHOLD = 3.00

# Bobot harus berjumlah 1.00 (100%).
AHP_WEIGHTS = {
    "Pekerjaan": 0.20,
    "Penghasilan": 0.30,
    "Status Tempat Tinggal": 0.15,
    "Kondisi Rumah": 0.20,
    "Pendidikan": 0.15,
}

AHP_SCORE_COLUMNS = {
    "Pekerjaan": "skor_pekerjaan",
    "Penghasilan": "skor_penghasilan",
    "Status Tempat Tinggal": "skor_status_tempat_tinggal",
    "Kondisi Rumah": "skor_kondisi_rumah",
    "Pendidikan": "skor_pendidikan",
}

COLUMN_ALIASES = {
    "no_kk": "nomor_kk",
    "no kk": "nomor_kk",
    "nomor kk": "nomor_kk",
    "nomor_kk": "nomor_kk",
    "nama pengurus": "nama_kepala_keluarga",
    "nama_pengurus": "nama_kepala_keluarga",
    "nama_pengurus_keluarga": "nama_kepala_keluarga",
    "nama kepala keluarga": "nama_kepala_keluarga",
    "nama_kepala_keluarga": "nama_kepala_keluarga",
    "art": "jumlah_art",
    "jumlah art": "jumlah_art",
    "jumlah_art": "jumlah_art",
    "nilai pekerjaan": "skor_pekerjaan",
    "skor pekerjaan": "skor_pekerjaan",
    "nilai penghasilan": "skor_penghasilan",
    "skor penghasilan": "skor_penghasilan",
    "nilai status tempat tinggal": "skor_status_tempat_tinggal",
    "skor status tempat tinggal": "skor_status_tempat_tinggal",
    "nilai kondisi rumah": "skor_kondisi_rumah",
    "skor kondisi rumah": "skor_kondisi_rumah",
    "nilai pendidikan": "skor_pendidikan",
    "skor pendidikan": "skor_pendidikan",
    "nilai ahp": "nilai_ahp",
    "nilai_ahp": "nilai_ahp",
    "status pkh": "status_pkh",
    "status_pkh": "status_pkh",
}


# =========================================================
# TAMPILAN
# =========================================================
def set_background() -> None:
    """Memasang gambar background lokal dari folder yang sama dengan app.py."""
    background_candidates = [
        BASE_DIR / "background.jpeg",
    ]

    background_path = next(
        (path for path in background_candidates if path.exists()),
        None,
    )

    if background_path is not None:
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(
            background_path.suffix.lower(),
            "image/jpeg",
        )

        encoded_image = base64.b64encode(
            background_path.read_bytes()
        ).decode("utf-8")

        background_source = (
            f'url("data:{mime_type};base64,{encoded_image}")'
        )
    else:
        # Background cadangan jika file gambar lokal belum ditemukan.
        background_source = (
            'url("https://images.unsplash.com/'
            'photo-1497366754035-f200968a6e72")'
        )

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image:
                linear-gradient(
                    rgba(255, 255, 255, 0.55),
                    rgba(255, 255, 255, 0.55)
                ),
                {background_source};
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}

        .block-container {{
            background-color: rgba(255, 255, 255, 0.88);
            padding: 30px;
            border-radius: 15px;
        }}

        section[data-testid="stSidebar"] {{
            background-color: rgba(255, 255, 255, 0.92);
        }}

        div.stButton > button {{
            border-radius: 10px;
            min-height: 45px;
            font-size: 16px;
            font-weight: bold;
        }}

        h1 {{
            color: #0b3d91;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# UTILITAS DATA
# =========================================================
def normalize_column_name(column: Any) -> str:
    """Membersihkan dan menyeragamkan nama kolom CSV."""
    cleaned = str(column).strip()
    lowered = cleaned.lower()

    if lowered in COLUMN_ALIASES:
        return COLUMN_ALIASES[lowered]

    # Kolom komponen PKH dibuat huruf kapital agar konsisten.
    if lowered.upper() in PKH_COLUMNS:
        return lowered.upper()

    return cleaned


def load_recipient_data() -> Optional[pd.DataFrame]:
    """Membaca data penerima dan mengembalikan DataFrame yang sudah dibersihkan."""
    if not DATA_PATH.exists():
        st.error(f"File data tidak ditemukan: {DATA_PATH}")
        return None

    try:
        df = pd.read_csv(DATA_PATH, dtype=str, keep_default_na=False)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as error:
        st.error(f"File penerima.csv tidak dapat dibaca: {error}")
        return None

    if df.empty:
        st.warning("File penerima.csv masih kosong.")
        return df

    df.columns = [normalize_column_name(column) for column in df.columns]

    # Hindari spasi dan akhiran .0 pada nomor KK hasil ekspor Excel.
    if "nomor_kk" in df.columns:
        df["nomor_kk"] = (
            df["nomor_kk"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )

    # Abaikan baris rekap TOTAL agar tidak dihitung sebagai keluarga.
    total_mask = pd.Series(False, index=df.index)

    if "nomor_kk" in df.columns:
        total_mask |= (
            df["nomor_kk"].astype(str).str.strip().str.upper() == "TOTAL"
        )

    if "nama_kepala_keluarga" in df.columns:
        total_mask |= (
            df["nama_kepala_keluarga"]
            .astype(str)
            .str.strip()
            .str.upper()
            == "TOTAL"
        )

    df = df.loc[~total_mask].copy()

    # Hapus baris yang benar-benar kosong pada identitas keluarga.
    identity_columns = [
        column
        for column in ["nomor_kk", "nama_kepala_keluarga"]
        if column in df.columns
    ]
    if identity_columns:
        has_identity = (
            df[identity_columns]
            .astype(str)
            .apply(lambda row: row.str.strip().ne("").any(), axis=1)
        )
        df = df.loc[has_identity].copy()

    return df.reset_index(drop=True)


def to_number(value: Any, default: float = 0.0) -> float:
    """Mengubah nilai CSV menjadi angka tanpa membuat aplikasi berhenti."""
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    # Mendukung angka desimal yang memakai koma.
    text = text.replace(",", ".")

    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def calculate_pkh_score(row: pd.Series) -> float:
    """Menjumlahkan seluruh komponen PKH yang tersedia pada satu baris."""
    return sum(to_number(row.get(column, 0)) for column in PKH_COLUMNS)


def normalize_status_pkh(value: Any) -> str:
    """Menyeragamkan penulisan status PKH dari file CSV."""
    status = str(value).strip().upper()

    if status in {
        "PENERIMA PKH",
        "CALON PENERIMA PKH",
        "TERMASUK PENERIMA PKH",
    }:
        return "CALON PENERIMA PKH"

    if status in {
        "BUKAN PENERIMA PKH",
        "TIDAK PENERIMA PKH",
        "TIDAK TERMASUK PENERIMA PKH",
        "TIDAK TERMASUK CALON PENERIMA PKH",
        "TIDAK",
    }:
        return "BUKAN PENERIMA PKH"

    return ""


def add_pkh_status(df: pd.DataFrame) -> pd.DataFrame:
    """Menentukan status memakai Status PKH atau Nilai AHP.

    Prioritas:
    1. Kolom status_pkh dari CSV.
    2. Kolom nilai_ahp dengan ambang 3,00.
    3. Komponen AUD–HAM sebagai cadangan untuk file lama.
    """
    result = df.copy()
    result["skor_pkh"] = result.apply(calculate_pkh_score, axis=1)

    # Status lama dari CSV, bila tersedia.
    if "status_pkh" in result.columns:
        status_file = result["status_pkh"].apply(normalize_status_pkh)
    else:
        status_file = pd.Series("", index=result.index, dtype="object")

    # Status berdasarkan nilai AHP.
    if "nilai_ahp" in result.columns:
        result["nilai_ahp"] = pd.to_numeric(
            result["nilai_ahp"]
            .astype(str)
            .str.replace(",", ".", regex=False),
            errors="coerce",
        )

        status_ahp = result["nilai_ahp"].apply(
            lambda value: (
                "CALON PENERIMA PKH"
                if pd.notna(value) and value >= AHP_THRESHOLD
                else "BUKAN PENERIMA PKH"
            )
        )
    else:
        # Cadangan untuk format CSV lama yang belum memiliki nilai AHP.
        status_ahp = result["skor_pkh"].apply(
            lambda score: (
                "CALON PENERIMA PKH"
                if score >= 1
                else "BUKAN PENERIMA PKH"
            )
        )

    result["status_pkh"] = status_file.where(status_file != "", status_ahp)
    return result


def available_display_limit(total_rows: int) -> list[int]:
    """Membuat pilihan jumlah baris yang relevan dengan ukuran data."""
    standard_limits = [10, 25, 50, 68, 100]
    limits = [limit for limit in standard_limits if limit < total_rows]
    limits.append(max(total_rows, 1))
    return sorted(set(limits))


# =========================================================
# LOGIN
# =========================================================
def hash_password(password: str) -> str:
    """Mengubah password menjadi hash SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def load_users() -> list[dict[str, Any]]:
    """Membaca dan memvalidasi daftar pengguna dari users.json."""
    if not USERS_PATH.exists():
        st.error(f"File pengguna tidak ditemukan: {USERS_PATH}")
        return []

    try:
        with USERS_PATH.open("r", encoding="utf-8") as file:
            users = json.load(file)
    except (json.JSONDecodeError, OSError) as error:
        st.error(f"File users.json tidak dapat dibaca: {error}")
        return []

    if not isinstance(users, list):
        st.error("Format users.json harus berupa daftar/list pengguna.")
        return []

    valid_users = []
    for user in users:
        if not isinstance(user, dict):
            continue
        if user.get("username") and user.get("password_hash"):
            valid_users.append(user)

    return valid_users


def check_login(username: str, password: str) -> Optional[dict[str, Any]]:
    password_hash = hash_password(password)
    normalized_username = username.strip()

    for user in load_users():
        if (
            str(user.get("username", "")).strip() == normalized_username
            and str(user.get("password_hash", "")) == password_hash
        ):
            return user

    return None


def login_page() -> None:
    st.markdown(
        """
        <div style="
            text-align: center;
            margin-top: 10px;
            margin-bottom: 24px;
        ">
            <h1 style="
                margin-bottom: 8px;
                color: #0b3d91;
            ">
                Login Admin
            </h1>
            <p style="
                margin: 0;
                font-size: 16px;
                color: #333333;
            ">
                Masuk ke Sistem Calon Penerima PKH Menggunakan  Metode AHP.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Masukkan username")
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Masukkan password",
        )
        login_button = st.form_submit_button("Login", use_container_width=True)

    if not login_button:
        return

    if not username.strip() or not password:
        st.warning("Username dan password wajib diisi.")
        return

    user = check_login(username, password)

    if user is None:
        st.error("Username atau password salah.")
        return

    st.session_state["logged_in"] = True
    st.session_state["user"] = user
    st.rerun()


def logout() -> None:
    """Menghapus seluruh sesi login pengguna."""
    st.session_state.clear()
    st.rerun()


# =========================================================
# HALAMAN APLIKASI
# =========================================================
def dashboard_page() -> None:
    st.title("Dashboard PKH")

    user = st.session_state.get("user", {})
    username = user.get("username", "Petugas") if isinstance(user, dict) else "Petugas"
    st.success(f"Selamat datang, {username}.")

    df = load_recipient_data()
    if df is None or df.empty:
        return

    df = add_pkh_status(df)

    total_data = len(df)
    total_candidates = int((df["status_pkh"] == "CALON PENERIMA PKH").sum())
    total_non_candidates = total_data - total_candidates

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Data", total_data)
    col2.metric("Penerima PKH", total_candidates)
    col3.metric("Bukan Penerima", total_non_candidates)


def search_page() -> None:
    st.title("🔍 Cek Nomor KK")

    df = load_recipient_data()
    if df is None or df.empty:
        return

    if "nomor_kk" not in df.columns:
        st.error("Kolom nomor KK tidak ditemukan. Gunakan nama kolom 'no_kk' atau 'nomor_kk'.")
        return

    nomor_kk = st.text_input("Nomor KK", placeholder="Masukkan nomor KK")

    if not st.button("Cari", type="primary"):
        return

    nomor_kk = nomor_kk.strip().replace(" ", "")
    if not nomor_kk:
        st.warning("Nomor KK wajib diisi.")
        return

    nomor_kk_data = df["nomor_kk"].astype(str).str.replace(" ", "", regex=False)
    hasil = df.loc[nomor_kk_data == nomor_kk]

    if hasil.empty:
        st.error("Nomor KK tidak ditemukan.")
        return

    hasil_status = add_pkh_status(hasil)
    data = hasil_status.iloc[0]
    status = data.get("status_pkh", "BUKAN PENERIMA PKH")

    st.success("Data ditemukan.")
    st.subheader("Data Keluarga")
    st.write("**Nomor KK:**", data.get("nomor_kk", "-"))
    st.write("**Nama Kepala Keluarga:**", data.get("nama_kepala_keluarga", "-"))
    st.write("**Jumlah ART:**", data.get("jumlah_art", "-"))

    st.subheader("Kriteria PKH")
    kriteria_rows = []
    for column in PKH_COLUMNS:
        kriteria_rows.append(
            {
                "Kriteria": column,
                "Nilai": data.get(column, "0"),
            }
        )

    st.dataframe(pd.DataFrame(kriteria_rows), use_container_width=True, hide_index=True)

    st.subheader("Status")
    if status == "CALON PENERIMA PKH":
        nilai_ahp = data.get("nilai_ahp", "")
        if pd.notna(nilai_ahp) and str(nilai_ahp).strip():
            st.success(f"TERMASUK PENERIMA PKH — Nilai AHP: {float(nilai_ahp):.2f}")
        else:
            st.success("TERMASUK PENERIMA PKH")
    else:
        nilai_ahp = data.get("nilai_ahp", "")
        if pd.notna(nilai_ahp) and str(nilai_ahp).strip():
            st.error(f"BUKAN PENERIMA PKH — Nilai AHP: {float(nilai_ahp):.2f}")
        else:
            st.error("BUKAN PENERIMA PKH")


def data_penerima_page() -> None:
    st.title("📋 Data Penerima PKH")

    df = load_recipient_data()
    if df is None or df.empty:
        return

    df = add_pkh_status(df)

    penerima = df.loc[
        df["status_pkh"] == "CALON PENERIMA PKH"
    ].copy()

    bukan_penerima = df.loc[
        df["status_pkh"] == "BUKAN PENERIMA PKH"
    ].copy()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Data", len(df))
    col2.metric("Penerima PKH", len(penerima))
    col3.metric("Bukan Penerima", len(bukan_penerima))

    preferred_columns = [
        "nomor_kk",
        "nama_kepala_keluarga",
        "jumlah_art",
        "nilai_ahp",
        "status_pkh",
    ]
    display_columns = [
        column for column in preferred_columns if column in df.columns
    ]

    column_names = {
        "no": "No.",
        "nomor_kk": "Nomor KK",
        "nama_kepala_keluarga": "Nama Kepala Keluarga",
        "jumlah_art": "Jumlah ART",
        "nilai_ahp": "Nilai AHP",
        "status_pkh": "Status PKH",
    }

    def show_status_table(
        data: pd.DataFrame,
        empty_message: str,
        selectbox_key: str,
    ) -> None:
        if data.empty:
            st.warning(empty_message)
            return

        limit_options = available_display_limit(len(data))
        default_index = len(limit_options) - 1

        jumlah_data = st.selectbox(
            "Jumlah data yang ditampilkan",
            options=limit_options,
            index=default_index,
            key=selectbox_key,
        )

        table = data[display_columns].head(jumlah_data).copy()

        # Tambahkan nomor urut sebelum kolom Nomor KK.
        table.insert(0, "no", range(1, len(table) + 1))

        if "nilai_ahp" in table.columns:
            table["nilai_ahp"] = pd.to_numeric(
                table["nilai_ahp"],
                errors="coerce",
            ).round(2)

        st.dataframe(
            table.rename(columns=column_names),
            use_container_width=True,
            hide_index=True,
            column_config={
                "No.": st.column_config.NumberColumn(
                    "No.",
                    format="%d",
                ),
                "Nilai AHP": st.column_config.NumberColumn(
                    "Nilai AHP",
                    format="%.2f",
                ),
            },
        )

    tab_penerima, tab_bukan, tab_semua = st.tabs(
        [
            f"✅ Penerima PKH ({len(penerima)})",
            f"❌ Bukan Penerima PKH ({len(bukan_penerima)})",
            f"📋 Semua Data ({len(df)})",
        ]
    )

    with tab_penerima:
        st.subheader("Daftar Penerima PKH")
        show_status_table(
            penerima,
            "Belum ada data penerima PKH.",
            "limit_penerima_pkh",
        )

    with tab_bukan:
        st.subheader("Daftar Bukan Penerima PKH")
        show_status_table(
            bukan_penerima,
            "Belum ada data bukan penerima PKH.",
            "limit_bukan_penerima_pkh",
        )

    with tab_semua:
        st.subheader("Seluruh Data Keluarga")
        show_status_table(
            df,
            "Belum ada data keluarga.",
            "limit_semua_data_pkh",
        )


def data_kriteria_page() -> None:
    st.title("📊 Data Kriteria PKH")
    st.write(
        "Halaman ini menampilkan kriteria dan bobot yang digunakan "
        "dalam perhitungan metode AHP."
    )

    descriptions = {
        "Pekerjaan": "Jenis pekerjaan calon penerima",
        "Penghasilan": "Jumlah penghasilan keluarga",
        "Status Tempat Tinggal": "Status kepemilikan tempat tinggal",
        "Kondisi Rumah": "Kondisi rumah calon penerima",
        "Pendidikan": "Tingkat pendidikan keluarga",
    }

    rows = []
    for index, (criterion, weight) in enumerate(AHP_WEIGHTS.items(), start=1):
        rows.append(
            {
                "Kode": f"C{index}",
                "Nama Kriteria": criterion,
                "Bobot AHP": weight,
                "Persentase": f"{weight:.0%}",
                "Keterangan": descriptions[criterion],
            }
        )

    df_kriteria = pd.DataFrame(rows)
    st.subheader("Daftar Kriteria Penilaian")
    st.dataframe(df_kriteria, use_container_width=True, hide_index=True)
    st.caption(f"Total bobot: {sum(AHP_WEIGHTS.values()):.0%}")


def ensure_ahp_score_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Membuat kolom skor alternatif AHP yang belum tersedia.

    Nilai awal 1 dipakai agar kolom bisa langsung diedit. Nilai tersebut bukan
    hasil penilaian final dan harus disesuaikan oleh petugas pada skala 1–5.
    """
    result = df.copy()
    added_columns: list[str] = []

    for score_column in AHP_SCORE_COLUMNS.values():
        if score_column not in result.columns:
            result[score_column] = 1
            added_columns.append(score_column)

        result[score_column] = (
            pd.to_numeric(
                result[score_column].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            .fillna(1)
            .clip(lower=1, upper=5)
            .round()
            .astype(int)
        )

    return result, added_columns


def calculate_ahp_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """Menghitung kontribusi tiap kriteria, nilai akhir, dan ranking.

    Rumus yang digunakan adalah skor alternatif (1–5) dikalikan bobot kriteria
    hasil AHP. Dengan demikian, bagian ini merupakan weighted scoring dengan
    bobot yang berasal dari AHP.
    """
    ranking = df.copy()

    contribution_columns = {
        "Pekerjaan": "nilai_pekerjaan",
        "Penghasilan": "nilai_penghasilan",
        "Status Tempat Tinggal": "nilai_status_tempat_tinggal",
        "Kondisi Rumah": "nilai_kondisi_rumah",
        "Pendidikan": "nilai_pendidikan",
    }

    ranking["nilai_ahp"] = 0.0

    for criterion, score_column in AHP_SCORE_COLUMNS.items():
        numeric_score = (
            pd.to_numeric(
                ranking[score_column].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            .fillna(1)
            .clip(lower=1, upper=5)
        )

        ranking[score_column] = numeric_score.round().astype(int)
        contribution_column = contribution_columns[criterion]
        ranking[contribution_column] = numeric_score * AHP_WEIGHTS[criterion]
        ranking["nilai_ahp"] += ranking[contribution_column]

    sort_columns = ["nilai_ahp"]
    ascending = [False]
    if "skor_pkh" in ranking.columns:
        sort_columns.append("skor_pkh")
        ascending.append(False)

    ranking = ranking.sort_values(
        by=sort_columns,
        ascending=ascending,
        kind="stable",
    ).reset_index(drop=True)

    ranking["ranking"] = ranking.index + 1

    numeric_result_columns = [*contribution_columns.values(), "nilai_ahp"]
    ranking[numeric_result_columns] = ranking[numeric_result_columns].round(4)
    return ranking


def save_ahp_scores(
    source_df: pd.DataFrame,
    edited_df: pd.DataFrame,
) -> bool:
    """Menyimpan skor yang diedit kembali ke penerima.csv."""
    try:
        result = source_df.copy()

        for row_index in edited_df.index:
            if row_index not in result.index:
                continue

            for score_column in AHP_SCORE_COLUMNS.values():
                value = to_number(edited_df.loc[row_index, score_column], default=1)
                result.loc[row_index, score_column] = int(min(max(round(value), 1), 5))

        # Hitung ulang nilai AHP setelah skor diedit.
        result["nilai_ahp"] = 0.0
        for criterion, score_column in AHP_SCORE_COLUMNS.items():
            numeric_score = pd.to_numeric(
                result[score_column]
                .astype(str)
                .str.replace(",", ".", regex=False),
                errors="coerce",
            ).fillna(1).clip(lower=1, upper=5)

            result[score_column] = numeric_score.round().astype(int)
            result["nilai_ahp"] += numeric_score * AHP_WEIGHTS[criterion]

        result["nilai_ahp"] = result["nilai_ahp"].round(2)
        result["status_pkh"] = result["nilai_ahp"].apply(
            lambda value: (
                "PENERIMA PKH"
                if value >= AHP_THRESHOLD
                else "BUKAN PENERIMA PKH"
            )
        )

        result = result.drop(columns=["skor_pkh"], errors="ignore")
        result.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")
        return True
    except (OSError, PermissionError) as error:
        st.error(f"Skor AHP gagal disimpan: {error}")
        return False


def kelola_data_page() -> None:
    st.title("📊 Data Alternatif Calon Penerima PKH")
    st.write(
        "Masukkan skor setiap alternatif pada skala 1–5. Nilai akhir dihitung "
        "dengan rumus skor alternatif × bobot kriteria hasil AHP."
    )

    source_df = load_recipient_data()
    if source_df is None or source_df.empty:
        return

    source_df, added_columns = ensure_ahp_score_columns(source_df)

    # Seluruh keluarga menjadi alternatif yang harus diberi skor.
    # Penyaringan penerima dilakukan setelah nilai AHP dihitung.
    alternatif = source_df.copy()
    alternatif.insert(0, "no", range(1, len(alternatif) + 1))

    if alternatif.empty:
        st.warning("Belum ada data alternatif.")
        return

    if added_columns:
        st.info(
            "Kolom skor AHP telah dibuat otomatis dengan nilai awal 1. "
            "Silakan ubah nilainya sesuai hasil penilaian petugas."
        )

    st.markdown(
        "**Panduan skor:** 1 = sangat rendah, 2 = rendah, 3 = cukup, "
        "4 = tinggi, 5 = sangat tinggi."
    )

    editor_columns = [
        "no",
        "nomor_kk",
        "nama_kepala_keluarga",
        "jumlah_art",
        *AHP_SCORE_COLUMNS.values(),
    ]
    editor_columns = [
        column for column in editor_columns if column in alternatif.columns
    ]

    column_config = {
        "no": st.column_config.NumberColumn("No.", format="%d"),
        "nomor_kk": st.column_config.TextColumn("Nomor KK"),
        "nama_kepala_keluarga": st.column_config.TextColumn("Nama Kepala Keluarga"),
        "jumlah_art": st.column_config.TextColumn("Jumlah ART"),
        "skor_pekerjaan": st.column_config.NumberColumn(
            "Skor Pekerjaan", min_value=1, max_value=5, step=1, format="%d"
        ),
        "skor_penghasilan": st.column_config.NumberColumn(
            "Skor Penghasilan", min_value=1, max_value=5, step=1, format="%d"
        ),
        "skor_status_tempat_tinggal": st.column_config.NumberColumn(
            "Skor Status Tempat Tinggal",
            min_value=1,
            max_value=5,
            step=1,
            format="%d",
        ),
        "skor_kondisi_rumah": st.column_config.NumberColumn(
            "Skor Kondisi Rumah", min_value=1, max_value=5, step=1, format="%d"
        ),
        "skor_pendidikan": st.column_config.NumberColumn(
            "Skor Pendidikan", min_value=1, max_value=5, step=1, format="%d"
        ),
    }

    st.subheader("✏️ Input Skor Seluruh Alternatif")
    edited_scores = st.data_editor(
        alternatif[editor_columns],
        use_container_width=True,
        hide_index=True,
        disabled=[
            column
            for column in ["no", "nomor_kk", "nama_kepala_keluarga", "jumlah_art"]
            if column in editor_columns
        ],
        column_config=column_config,
        key="ahp_score_editor",
    )

    col1, col2 = st.columns(2)
    with col1:
        calculate_button = st.button(
            "Hitung Ranking AHP",
            type="primary",
            use_container_width=True,
        )
    with col2:
        save_button = st.button(
            "Simpan Skor ke CSV",
            use_container_width=True,
        )

    if save_button:
        if save_ahp_scores(source_df, edited_scores):
            st.success(f"Skor AHP berhasil disimpan ke {DATA_PATH.name}.")

    # Hasil ditampilkan langsung agar perubahan skor dapat dilihat tanpa harus
    # menunggu penyimpanan. Tombol hitung juga memberi umpan balik yang jelas.
    ranking_input = alternatif.copy()
    for score_column in AHP_SCORE_COLUMNS.values():
        ranking_input.loc[edited_scores.index, score_column] = edited_scores[score_column]

    ranking_semua = calculate_ahp_ranking(ranking_input)

    # Hasil akhir hanya menampilkan alternatif yang memenuhi ambang penerima.
    ranking_ahp = ranking_semua.loc[
        ranking_semua["nilai_ahp"] >= AHP_THRESHOLD
    ].copy()

    # Ranking dibuat ulang khusus untuk alternatif yang dinyatakan lolos.
    ranking_ahp = ranking_ahp.sort_values(
        by="nilai_ahp",
        ascending=False,
        kind="stable",
    ).reset_index(drop=True)
    ranking_ahp["ranking"] = ranking_ahp.index + 1
    ranking_ahp["status_pkh"] = "PENERIMA PKH"

    if calculate_button:
        st.success("Perhitungan dan ranking AHP berhasil diperbarui.")

    st.subheader("🏆 Hasil Perhitungan dan Ranking AHP")

    if ranking_ahp.empty:
        st.warning(
            "Belum ada alternatif yang memenuhi ambang Nilai AHP minimal "
            f"{AHP_THRESHOLD:.2f}."
        )
        return
    display_columns = [
        "ranking",
        "nomor_kk",
        "nama_kepala_keluarga",
        "skor_pekerjaan",
        "nilai_pekerjaan",
        "skor_penghasilan",
        "nilai_penghasilan",
        "skor_status_tempat_tinggal",
        "nilai_status_tempat_tinggal",
        "skor_kondisi_rumah",
        "nilai_kondisi_rumah",
        "skor_pendidikan",
        "nilai_pendidikan",
        "nilai_ahp",
        "status_pkh",
    ]
    display_columns = [
        column for column in display_columns if column in ranking_ahp.columns
    ]

    result_column_config = {
        "nomor_kk": "Nomor KK",
        "nama_kepala_keluarga": "Nama Kepala Keluarga",
        "skor_pekerjaan": "Skor Pekerjaan",
        "nilai_pekerjaan": "Nilai Pekerjaan (20%)",
        "skor_penghasilan": "Skor Penghasilan",
        "nilai_penghasilan": "Nilai Penghasilan (30%)",
        "skor_status_tempat_tinggal": "Skor Status Tinggal",
        "nilai_status_tempat_tinggal": "Nilai Status Tinggal (15%)",
        "skor_kondisi_rumah": "Skor Kondisi Rumah",
        "nilai_kondisi_rumah": "Nilai Kondisi Rumah (20%)",
        "skor_pendidikan": "Skor Pendidikan",
        "nilai_pendidikan": "Nilai Pendidikan (15%)",
        "nilai_ahp": "Nilai Akhir AHP",
        "status_pkh": "Status PKH",
        "ranking": "No.",
    }

    st.dataframe(
        ranking_ahp[display_columns].rename(columns=result_column_config),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Rumus nilai akhir: (Pekerjaan × 20%) + (Penghasilan × 30%) + "
        "(Status Tempat Tinggal × 15%) + (Kondisi Rumah × 20%) + "
        "(Pendidikan × 15%). Hanya alternatif dengan Nilai AHP minimal "
        f"{AHP_THRESHOLD:.2f} yang ditampilkan sebagai PENERIMA PKH."
    )


# =========================================================
# PROGRAM UTAMA
# =========================================================
def main() -> None:
    st.set_page_config(
        page_title="Aplikasi PKH",
        page_icon="📋",
        layout="wide",
    )

    set_background()

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        login_page()
        return

    menu = st.sidebar.radio(
        "Pilih Menu",
        [
            "Dashboard",
            "Data Kriteria",
            "Data Penerima PKH",
            "Cek Nomor KK",
            "Data Alternatif",
            "Logout",
        ],
    )

    if menu == "Dashboard":
        dashboard_page()
    elif menu == "Data Kriteria":
        data_kriteria_page()
    elif menu == "Data Penerima PKH":
        data_penerima_page()
    elif menu == "Cek Nomor KK":
        search_page()
    elif menu == "Data Alternatif":
        kelola_data_page()
    elif menu == "Logout":
        logout()


if __name__ == "__main__":
    main()
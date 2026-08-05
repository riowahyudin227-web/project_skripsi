import streamlit as st
import pandas as pd
import json
import hashlib
from pathlib import Path


# ===============================
# BACKGROUND APLIKASI
# ===============================
def set_background():

    st.markdown(
        """
        <style>

        .stApp {
            background-image: linear-gradient(
                rgba(255,255,255,0.55)
                rgba(255,255,255,0.55)
            ),
            url("https://images.unsplash.com/photo-1497366754035-f200968a6e72");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }

        .block-container {
            background-color: rgba(255,255,255,0.85);
            padding: 30px;
            border-radius: 15px;
        }

        section[data-testid="stSidebar"] {
            background-color: rgba(255,255,255,0.90);
        }

        div.stButton > button {
            border-radius: 10px;
            height: 45px;
            font-size: 16px;
            font-weight: bold;
        }

        h1 {
            color: #0b3d91;
        }

        </style>
        """,
        unsafe_allow_html=True
    )


USERS_PATH = Path("config/users.json")

def hash_password(password: str) -> str:
    """Mengubah password menjadi hash SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def load_users() -> list:
    """Membaca daftar pengguna dari users.json."""
    if not USERS_PATH.exists():
        st.error("File config/users.json tidak ditemukan.")
        return []

    try:
        with USERS_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        st.error("File users.json tidak dapat dibaca.")
        return []


def check_login(username: str, password: str):

    users = load_users()
    password_hash = hash_password(password)

    for user in users:
        if (
            user["username"] == username
            and user["password_hash"] == password_hash
        ):
            return user

    return None


def login_page():
    st.title("Login Petugas")
    st.write("Masukkan username dan password untuk melanjutkan.")

    with st.form("login_form"):
        username = st.text_input(
            "Username",
            placeholder="Masukkan username"
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Masukkan password"
        )

        login_button = st.form_submit_button("Login")

    if login_button:
        if not username.strip() or not password:
            st.warning("Username dan password wajib diisi.")
            return

        user = check_login(username, password)

        if user is not None:
            st.session_state["logged_in"] = True
            st.session_state["user"] = user

            st.success("Login berhasil.")
            st.rerun()
        else:
            st.error("Username atau password salah.")


def logout():
    """Menghapus sesi login pengguna."""
    st.session_state["logged_in"] = False
    st.session_state.pop("user", None)
    st.rerun()


def dashboard_page():
    st.title("Dashboard PKH")
    username = st.session_state["user"].get("username", "Petugas")
    st.success(f"Selamat datang, {username}.")


# TAMBAHKAN DI SINI

def search_page():

    st.title("🔍 Cek Nomor KK")

    DATA_PATH = Path("data/penerima.csv")

    if not DATA_PATH.exists():
        st.error("File penerima.csv tidak ditemukan")
        return

    df = pd.read_csv(DATA_PATH, dtype=str)
    df = df.fillna("")

    # membersihkan nama kolom
    df.columns = df.columns.str.strip()

    # sesuaikan nama kolom KK
    df = df.rename(columns={
        "no_kk": "nomor_kk",
        "nama_pengurus_keluarga": "nama_kepala_keluarga",
        "ART": "jumlah_art"
    })

    nomor_kk = st.text_input("Nomor KK")

    if st.button("Cari"):

        nomor_kk = nomor_kk.strip()

        hasil = df[df["nomor_kk"] == nomor_kk]

        if hasil.empty:
            st.error("Nomor KK tidak ditemukan")
            return

        st.success("Data ditemukan")

        data = hasil.iloc[0]

        st.subheader("Data Keluarga")

        st.write("Nomor KK :", data["nomor_kk"])

        if "nama_kepala_keluarga" in data:
            st.write(
                "Nama Kepala Keluarga :",
                data["nama_kepala_keluarga"]
            )

        if "jumlah_art" in data:
            st.write(
                "Jumlah ART :",
                data["jumlah_art"]
            )

        st.subheader("Kriteria PKH")

        kolom_pkh = [
            "AUD",
            "SD",
            "SMP",
            "SMA",
            "DB",
            "LU",
            "HAMIL",
            "HAM"
        ]

        skor = 0

        for kolom in kolom_pkh:
            nilai = data.get(kolom, "0")

            st.write(
                kolom,
                ":",
                nilai
            )

            try:
                skor += int(nilai)
            except:
                pass


        st.subheader("Status")

        if skor >= 1:
            st.success("TERMASUK PENERIMA PKH")
        else:
            st.error("TIDAK TERMASUK PENERIMA PKH")


def data_penerima_page():

    st.title("📋 Data Calon Penerima PKH")

    DATA_PATH = Path("data/penerima.csv")

    if not DATA_PATH.exists():
        st.error("File penerima.csv tidak ditemukan")
        return

    df = pd.read_csv(DATA_PATH, dtype=str)
    df = df.fillna("")

    # membersihkan nama kolom
    df.columns = df.columns.str.strip()

    # menyesuaikan nama kolom
    df = df.rename(columns={
        "no_kk": "nomor_kk",
        "nama_pengurus_keluarga": "nama_kepala_keluarga",
        "ART": "jumlah_art"
    })


    st.subheader("Daftar Penerima PKH")


    # hitung kriteria PKH
    kolom_pkh = [
        "AUD",
        "SD",
        "SMP",
        "SMA",
        "DB",
        "LU",
        "HAMIL",
        "HAM"
    ]


    def hitung_status(row):

        skor = 0

        for kolom in kolom_pkh:
            nilai = row.get(kolom, "0")

            try:
                skor += int(nilai)
            except:
                pass

        if skor >= 1:
            return "CALON PENERIMA PKH"
        else:
            return "TIDAK PENERIMA PKH"


    df["status_pkh"] = df.apply(hitung_status, axis=1)


    # hanya tampilkan calon penerima PKH
    penerima = df[df["status_pkh"] == "CALON PENERIMA PKH"]


    if penerima.empty:
        st.warning("Belum ada data penerima PKH")
    else:

        kolom_tampil = []

        if "nomor_kk" in penerima.columns:
            kolom_tampil.append("nomor_kk")

        if "nama_kepala_keluarga" in penerima.columns:
            kolom_tampil.append("nama_kepala_keluarga")

        if "jumlah_art" in penerima.columns:
            kolom_tampil.append("jumlah_art")

        kolom_tampil.append("status_pkh")


        jumlah_data = st.selectbox(
    "Jumlah data yang ditampilkan",
    [10, 20, 30, 50, 68]
)

        st.dataframe(
    penerima[kolom_tampil].head(jumlah_data),
    width="stretch"
)

def data_kriteria_page():

    st.title("📊 Data Kriteria PKH")

    st.write(
        "Halaman ini menampilkan kriteria yang digunakan "
        "dalam proses perhitungan metode AHP."
    )

    data_kriteria = {
        "Kode": [
            "C1",
            "C2",
            "C3",
            "C4",
            "C5"
        ],

        "Nama Kriteria": [
            "Pekerjaan",
            "Penghasilan",
            "Status Tempat Tinggal",
            "Kondisi Rumah",
            "Pendidikan"
        ],

        "Bobot AHP": [
            0.20,
            0.30,
            0.15,
            0.10,
            0.15
        ],

        "Keterangan": [
            "Jenis pekerjaan calon penerima",
            "Jumlah penghasilan keluarga",
            "Status kepemilikan tempat tinggal",
            "Kondisi rumah calon penerima",
            "Tingkat pendidikan keluarga"
        ]
    }


    df_kriteria = pd.DataFrame(data_kriteria)


    st.subheader("Daftar Kriteria Penilaian")

    st.dataframe(
    df_kriteria,
    width="stretch"
)

def kelola_data_page():

    st.title("📊 Data Alternatif Calon Penerima PKH")

    st.write(
        "Halaman ini menampilkan data calon penerima PKH "
        "beserta hasil ranking berdasarkan metode AHP."
    )


    DATA_PATH = Path("data/penerima.csv")

    if not DATA_PATH.exists():
        st.error("File penerima.csv tidak ditemukan")
        return


    df = pd.read_csv(DATA_PATH, dtype=str)

    df = df.fillna("")
    df.columns = df.columns.str.strip()


    def status_pkh(row):

        skor = 0

        for kolom in [
            "AUD","SD","SMP","SMA",
            "DB","LU","HAMIL","HAM"
        ]:
            try:
                skor += int(row.get(kolom,0))
            except:
                pass

        return "PENERIMA PKH" if skor > 0 else "TIDAK"


    df["status_pkh"] = df.apply(status_pkh, axis=1)


    alternatif = df.head(68)


    hasil = []


    for index,row in alternatif.iterrows():

        pekerjaan = 3 if row["status_pkh"]=="PENERIMA PKH" else 3


        art = int(row.get("ART",0))


        if art >= 3:
            penghasilan = 2
        elif art == 2:
            penghasilan = 3
        else:
            penghasilan = 5


        kondisi_rumah = 4
        status_tempat_tinggal = 3
        pendidikan = 2


        nilai_ahp = (
            pekerjaan*0.40 +
            penghasilan*0.30 +
            kondisi_rumah*0.20 +
            status_tempat_tinggal*0.15 +
            pendidikan*0.15
        )


        hasil.append({

            "Nama":
            row.get("nama_pengurus_keluarga",""),

            "Pekerjaan":
            pekerjaan,

            "Penghasilan":
            penghasilan,

            "Kondisi Rumah":
            kondisi_rumah,

            "Status Tempat Tinggal":
            status_tempat_tinggal,

            "Pendidikan":
            pendidikan,

            "Nilai AHP":
            round(nilai_ahp,2)

        })


    ranking = pd.DataFrame(hasil)


    ranking = ranking.sort_values(
        "Nilai AHP",
        ascending=False
    )


    ranking["Ranking"] = range(
        1,
        len(ranking)+1
    )


    st.subheader(
        "🏆 Hasil Ranking Calon Penerima PKH"
    )


    st.dataframe(
        ranking,
        width="stretch"
    )
    DATA_PATH = Path("data/penerima.csv")

    if not DATA_PATH.exists():
        st.error("File penerima.csv tidak ditemukan")
        return

    df = pd.read_csv(DATA_PATH, dtype=str)
    df = df.fillna("")

    df.columns = df.columns.str.strip()


    # daftar kriteria PKH
    kriteria = [
        "AUD",
        "SD",
        "SMP",
        "SMA",
        "DB",
        "LU",
        "HAMIL",
        "HAM"
    ]


    # hitung skor
    def hitung_skor(row):

        skor = 0

        for kolom in kriteria:
            try:
                skor += int(row.get(kolom, 0))
            except:
                pass

        return skor


    df["nilai"] = df.apply(hitung_skor, axis=1)


    # ranking berdasarkan nilai tertinggi
    df = df.sort_values(
        by="nilai",
        ascending=False
    )


    df["ranking"] = range(
        1,
        len(df)+1
    )


    st.subheader("🏆 Hasil Ranking Penerima PKH")


    kolom = []


    if "no_kk" in df.columns:
        kolom.append("no_kk")

    if "nama_pengurus_keluarga" in df.columns:
        kolom.append("nama_pengurus_keluarga")

    kolom += [
        "nilai",
        "ranking"
    ]


    st.dataframe(
        df[kolom],
        width="stretch"
    )


def main():

    st.set_page_config(
        page_title="Aplikasi PKH",
        page_icon="📋",
        layout="wide"
    )

    set_background()

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False


    if not st.session_state["logged_in"]:
        login_page()
        return


    # TAMBAHKAN BAGIAN INI DI SINI
    menu = st.sidebar.radio(
    "Pilih Menu",
    [
        "Dashboard",
        "Data Kriteria",
        "Data Calon Penerima PKH",
        "Cek Nomor KK",
        "Data Alternatif",
        "Logout"
    ]
)


    if menu == "Dashboard":
        dashboard_page()

    elif menu == "Data Kriteria":
        data_kriteria_page()

    elif menu == "Cek Nomor KK":
        search_page()

    elif menu == "Data Calon Penerima PKH":
        data_penerima_page()

    elif menu == "Data Alternatif":
        kelola_data_page()

    elif menu == "Logout":
        logout()


if __name__ == "__main__":
    main()

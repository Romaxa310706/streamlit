#я добавил кэш для смягчения нагрузки (может быть будут большие файлы)
import pandas as pd
import streamlit as st
import plotly.express as px
import requests
from datetime import datetime

# Функция для загрузки данных
@st.cache_data
def load_data(file):
    try:
        df = pd.read_csv(file, parse_dates=["timestamp"])
        required_columns = {"city", "timestamp", "temperature", "season"}
        if not required_columns.issubset(df.columns):
            st.error("Ошибка: отсутствуют необходимые столбцы в загруженном файле!")
            return None
        return df
    except Exception as e:
        st.error(f"Ошибка при загрузке данных: {e}")
        return None

# Функция для расчета скользящего среднего
@st.cache_data
def calculate_moving_average(df, window=30):
    df["moving_avg"] = df.groupby("city")["temperature"].transform(
        lambda x: x.rolling(window=window, min_periods=1).mean())
    return df

# Функция для выявления аномалий
@st.cache_data
def detect_anomalies(df):
    stats = df.groupby(["city", "season"])["temperature"].agg(['mean', 'std']).reset_index()
    df = df.merge(stats, on=["city", "season"], how="left")
    df["is_anomaly"] = (df["temperature"] < df["mean"] - 2 * df["std"]) | (
            df["temperature"] > df["mean"] + 2 * df["std"])
    return df

# Функция для получения текущей температуры
def get_current_temperature(city, api_key):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(url)
    data = response.json()
    if response.status_code == 200:
        return data['main']['temp']
    else:
        st.error("Ошибка при получении данных от OpenWeatherMap. Проверьте API ключ.")
        return None

# Интерфейс Streamlit
st.title("Анализ климатических данных")
file = st.file_uploader("Загрузите CSV с историческими данными", type=["csv"])

if file:
    df = load_data(file)
    if df is not None:
        cities = df["city"].unique()
        selected_city = st.selectbox("Выберите город", cities)
        df = df[df["city"] == selected_city]

        df = calculate_moving_average(df)
        df = detect_anomalies(df)

        st.subheader("Выберите период для анализа")
        start_date = st.date_input("Начало периода", df["timestamp"].min())
        end_date = st.date_input("Конец периода", df["timestamp"].max())
        df_period = df[(df["timestamp"] >= pd.to_datetime(start_date)) & (df["timestamp"] <= pd.to_datetime(end_date))]

        # Линейный график температур
        fig_period = px.line(df_period, x="timestamp", y="temperature",
                             title=f"Температура в {selected_city} (Период: {start_date} - {end_date})",
                             labels={"temperature": "°C"})
        fig_period.add_scatter(x=df_period[df_period["is_anomaly"]]["timestamp"],
                               y=df_period[df_period["is_anomaly"]]["temperature"], mode="markers", name="Аномалии",
                               marker=dict(color="red"))
        st.plotly_chart(fig_period)

        # Таблица со стандартным и средним отклонением
        stats_table = df_period[["temperature"]].agg(["mean", "std"]).reset_index()
        stats_table.columns = ["Показатель", "Значение"]
        st.subheader("Статистические показатели температуры")
        st.dataframe(stats_table)

        # Гистограмма температур
        st.subheader("Распределение температур")
        fig_hist = px.histogram(df, x="temperature", nbins=30, title="Гистограмма температур",
                                labels={"temperature": "Температура (°C)"}, marginal="rug")
        st.plotly_chart(fig_hist)

        # Boxplot для сезонных температур
        st.subheader("Ящик с усами (Boxplot) для сезонных температур")
        fig_box = px.box(df, x="season", y="temperature", title="Температура по сезонам",
                         labels={"season": "Сезон", "temperature": "Температура (°C)"}, color="season")
        st.plotly_chart(fig_box)

        # Scatter plot: Температура vs Время
        st.subheader("Температура во времени")
        fig_scatter = px.scatter(df, x="timestamp", y="temperature", color="season",
                                 title="Температура во времени", labels={"temperature": "Температура (°C)"})
        st.plotly_chart(fig_scatter)

        api_key = st.text_input("Введите API-ключ OpenWeatherMap")
        if api_key:
            current_temp = get_current_temperature(selected_city, api_key)
            if current_temp is not None:
                current_month = datetime.now().month
                current_season = "winter" if current_month in [12, 1, 2] else \
                                 "spring" if current_month in [3, 4, 5] else \
                                 "summer" if current_month in [6, 7, 8] else "autumn"
                season_data = df[df["season"] == current_season]
                mean_temp = season_data["temperature"].mean()
                std_temp = season_data["temperature"].std()

                st.write(f"Текущая температура в {selected_city}: {current_temp}°C")
                if mean_temp - 2 * std_temp <= current_temp <= mean_temp + 2 * std_temp:
                    st.success(f"Температура в пределах нормы для текущего сезона ({current_season}).")
                else:
                    st.warning(f"Температура {current_temp}°C отклоняется от нормальных значений для сезона {current_season}.")

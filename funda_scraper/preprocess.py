"""Preprocess raw data scraped from Funda"""
from typing import Any

import pandas as pd
from funda_scraper.config.core import config
from datetime import datetime
from datetime import timedelta
import warnings
import locale


def clean_price(x: str) -> int:
    """Clean the 'price' and transform from string to integer."""
    try:
        return int(str(x).split(" ")[1].replace(".", ""))
    except (ValueError,IndexError):
        warnings.warn(f"Could not clean {x}, returning 0 (which will be deleted)")
        return 0


def clean_year(x: str) -> int:
    """Clean the 'year' and transform from string to integer"""
    if len(x) == 4:
        return int(x)
    elif x.find("-") != -1:
        return int(x.split("-")[0])
    elif x.find("Voor") != -1:
        return int(x.split(" ")[1])
    else:
        warnings.warn(f"Could not process {x}")
        return 0


def clean_living_area(x: str) -> int:
    """Clean the 'living_area' and transform from string to integer"""
    try:
        return int(str(x).replace(",", "").split(" m²")[0])
    except (IndexError, ValueError):
        return 0


def find_n_room(x: str) -> int:
    """Find the number of rooms from a string"""
    if x.find("kamer") != -1:
        return int(str(x).split("kamer")[0].strip())
    else:
        return 0


def find_n_bedroom(x: str) -> int:
    """Find the number of bedrooms from a string"""
    if x.find("slaapkamer") != -1:
        return int(x.split(" ")[2].replace("(", ""))
    else:
        return 0


def find_n_bathroom(x: str) -> int:
    """Find the number of bathrooms from a string"""
    if x.find("badkamer") != -1:
        return int(str(x).split("badkamer")[0].strip())
    else:
        return 0


def map_dutch_month(x: str) -> str:
    """Map the month from Dutch to English."""
    month_mapping = {
        "januari": "January",
        "februari": "February",
        "maart": "March",
        "mei": "May",
        "juni": "June",
        "juli": "July",
        "augustus": "August",
        "oktober": "October",
    }
    for k, v in month_mapping.items():
        if x.find(k) != -1:
            x = x.replace(k, v)
    return x


def get_neighbor(x: str) -> str:
    """Find the neighborhood name."""
    city = x.split("/")[0].replace("-", " ")
    return x.lower().split(city)[-1]


def clean_energy_label(x: str) -> str:
    """Clean the energy labels."""
    try:
        x = x.split(" ")[0]
        if x.find("A+") != -1:
            return ">A+"
        else:
            return x
    except IndexError:
        return x


def clean_list_date(x: str) -> Any:
    """Transform the date from string to datetime object."""
    def delta_now(d):
        t = timedelta(days=d)
        return datetime.now().date() - t
    try:
        if (
            x.find("€") != -1
            or x.find("na") != -1
            or x.find("Onbepaalde tijd") != -1
        ):
            return "na"
        elif x.find("maand") != -1:
            return delta_now(int(x.split("maand")[0].strip()[0]) * 30) # TODO: what is the month doing in here?
        elif x.find("weken") != -1:
            return delta_now(int(x.split("weken")[0].strip()[0]) * 7) # TODO: what is the month doing in here?
        elif x.find("Vandaag") != -1:
            return delta_now(0)
        elif x.find("dag") != -1:
            return delta_now(int(x.split("dag")[0].strip())) # TODO: what is the month doing in here?
        else:
            locale.setlocale(locale.LC_TIME,'nl_NL') # en_us.utf-8
            return datetime.strptime(x, "%d %B %Y")
    except ValueError:
        print(f"Not able to interpret {x}, returning 'na' and will be removed")
        warnings.warn(f"Not able to interpret {x}, returning 'na' and will be removed")
        return "na"


def preprocess_data(df: pd.DataFrame, is_past: bool) -> pd.DataFrame:
    """
    Clean the raw dataframe from scraping.
    Indicate whether it includes historical data sicne the columns would be different.

    :param df: raw dataframe from scraping
    :param is_past: whether it scraped past data
    :return: clean dataframe
    """

    df = df.dropna()
    keep_cols = config.keep_cols.selling_data
    keep_cols_sold = keep_cols + config.keep_cols.sold_data

    # Info
    df["house_id"] = df["url"].apply(lambda x: int(x.split("/")[-2].split("-")[1]))
    df["house_type"] = df["url"].apply(lambda x: x.split("/")[-2].split("-")[0])
    df = df[df["house_type"].isin(["appartement", "huis"])]

    # Price
    price_col = "price_sold" if is_past else "price"
    df["price"] = df[price_col].apply(clean_price)
    df = df[df["price"] != 0]
    df["living_area"] = df["living_area"].apply(clean_living_area)
    df = df[df["living_area"] != 0]
    df["price_m2"] = round(df.price / df.living_area, 1)

    # Location
    df["zip"] = df["zip_code"].apply(lambda x: x[:7])

    # House layout
    df["room"] = df["num_of_rooms"].apply(find_n_room)
    df["bedroom"] = df["num_of_rooms"].apply(find_n_bedroom)
    df["bathroom"] = df["num_of_bathrooms"].apply(find_n_bathroom)
    df["energy_label"] = df["energy_label"].apply(clean_energy_label)
    df["has_balcony"] = df["exteriors"].apply(
        lambda x: 1 if str(x).find("Balkon") != -1 else 0
    )
    df["has_garden"] = df["exteriors"].apply(
        lambda x: 1 if str(x).find("Tuin") != -1 else 0
    )

    # Time
    df["year_built"] = df["year"].apply(clean_year).astype(int)
    df["house_age"] = 2023 - df["year_built"]

    if not is_past:
        # Only check current data
        df["date_list"] = df.listed_since.apply(clean_list_date)
        df = df[df["date_list"] != "na"]
        df["date_list"] = pd.to_datetime(df["date_list"])

    else:
        # Only check past data
        df = df[(df["date_sold"] != "na") & (df["date_list"] != "na")]
        df["date_sold"] = df["date_sold"].apply(map_dutch_month)
        df = df.dropna()
        locale.setlocale(locale.LC_TIME,'nl_NL') # en_us.utf-8
        df["date_list"] = pd.to_datetime(df["date_list"], format="%d %B %Y")
        locale.setlocale(locale.LC_TIME,'en_us') # en_us.utf-8
        df["date_sold"] = pd.to_datetime(df["date_sold"])
        df["ym_sold"] = df["date_sold"].apply(lambda x: x.to_period("M").to_timestamp())
        df["year_sold"] = df["date_sold"].apply(lambda x: x.year)

        # Term
        df["term_days"] = df["date_sold"] - df["date_list"]
        df["term_days"] = df["term_days"].apply(lambda x: x.days)
        keep_cols = keep_cols_sold

    df["ym_list"] = df["date_list"].apply(lambda x: x.to_period("M").to_timestamp())
    df["year_list"] = df["date_list"].apply(lambda x: x.year)

    return df[keep_cols].reset_index(drop=True)

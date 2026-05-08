"""Optional Streamlit demo UI for the Netflix Catalog API."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PAGE_SIZE = 5


def call_api(
    api_base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Call the FastAPI backend and return JSON data or an error message."""
    url = f"{api_base_url.rstrip('/')}{path}"

    if query_params:
        clean_params = {
            key: value
            for key, value in query_params.items()
            if value is not None and value != ""
        }

        if clean_params:
            url = f"{url}?{urlencode(clean_params)}"

    body = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(request, timeout=90) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body), None
    except HTTPError as error:
        detail = error.read().decode("utf-8")
        return None, f"API error {error.code}: {detail}"
    except URLError as error:
        return None, f"Could not connect to API server: {error.reason}"
    except TimeoutError:
        return None, "API request timed out."


def show_health(api_base_url: str) -> None:
    """Show the /health endpoint result."""
    st.subheader("Health Check")

    if st.button("Check API"):
        data, error = call_api(api_base_url, "/health")

        if error:
            st.error(error)
            return

        st.success("API is running.")
        st.json(data)


def show_titles(api_base_url: str) -> None:
    """Show the /titles endpoint with required filters and pagination."""
    st.subheader("List Titles")

    st.write(
        "This calls `GET /titles` with the required filters: "
        "`country`, `release_year`, `type`, `rating`, and pagination."
    )

    col1, col2 = st.columns(2)

    with col1:
        country = st.text_input("Country", value="India")
        release_year = st.text_input("Release year", value="")
        title_type = st.selectbox("Type", ["", "Movie", "TV Show"])

    with col2:
        rating = st.text_input("Rating", value="")
        page = st.number_input("Result page", min_value=1, value=1)
        page_size = st.number_input(
            "Results per page",
            min_value=1,
            max_value=100,
            value=DEFAULT_PAGE_SIZE,
        )

    if st.button("Search titles"):
        data, error = call_api(
            api_base_url,
            "/titles",
            query_params={
                "country": country,
                "release_year": release_year,
                "type": title_type,
                "rating": rating,
                "page": page,
                "page_size": page_size,
            },
        )

        if error:
            st.error(error)
            return

        if data is None:
            st.warning("No response returned.")
            return

        st.write(f"Total matches: **{data['total']}**")
        st.write(f"Showing result page **{data['page']}** with **{data['page_size']}**")

        if not data["items"]:
            st.info("No titles found.")
            return

        for item in data["items"]:
            with st.expander(f"{item['title']} ({item['release_year']})"):
                st.write(f"**show_id:** {item['show_id']}")
                st.write(f"**Type:** {item['type']}")
                st.write(f"**Rating:** {item['rating']}")
                st.write(
                    f"**Duration:** {item['duration_value']} {item['duration_unit']}"
                )
                st.write(f"**Date added:** {item['date_added']}")
                st.write(f"**Countries:** {', '.join(item['countries'])}")
                st.write(f"**Genres:** {', '.join(item['genres'])}")
                st.write(f"**Directors:** {', '.join(item['directors'])}")
                st.write(f"**Cast:** {', '.join(item['cast'][:10])}")
                st.write(item["description"])


def show_title_by_id(api_base_url: str) -> None:
    """Show the /titles/{show_id} endpoint."""
    st.subheader("Fetch Title by ID")

    st.write("This calls `GET /titles/{show_id}`.")

    show_id = st.text_input("show_id", value="81075235")

    if st.button("Fetch title"):
        data, error = call_api(api_base_url, f"/titles/{show_id}")

        if error:
            st.error(error)
            return

        if data is None:
            st.warning("No response returned.")
            return

        st.json(data)


def show_stats(api_base_url: str) -> None:
    """Show the /stats endpoint."""
    st.subheader("Catalogue Stats")

    st.write("This calls `GET /stats`.")

    if st.button("Load stats"):
        data, error = call_api(api_base_url, "/stats")

        if error:
            st.error(error)
            return

        if data is None:
            st.warning("No response returned.")
            return

        st.metric("Total titles", data["total_titles"])

        st.markdown("### Count by type")
        st.json(data["count_by_type"])

        st.markdown("### Top countries")
        st.dataframe(data["top_countries"], use_container_width=True)


def show_ask(api_base_url: str) -> None:
    """Show the /ask RAG endpoint."""
    st.subheader("Ask the Catalogue")

    st.write("This calls `POST /ask`.")

    question = st.text_area(
        "Question",
        value="Suggest me an Indian comedy movie",
        height=120,
    )

    if st.button("Ask"):
        data, error = call_api(
            api_base_url,
            "/ask",
            method="POST",
            payload={"question": question},
        )

        if error:
            st.error(error)
            return

        if data is None:
            st.warning("No response returned.")
            return

        st.markdown("### Answer")
        st.write(data["answer"])

        st.markdown("### Sources")
        if data["sources"]:
            st.dataframe(data["sources"], use_container_width=True)
        else:
            st.info("No sources returned.")


def main() -> None:
    """Run the optional Streamlit demo app."""
    st.set_page_config(page_title="Netflix Catalog Demo", layout="wide")

    st.title("Netflix Catalog Q&A Demo")
    st.write(
        "This optional demo calls the FastAPI backend endpoints. "
        "Start the API server before using this UI."
    )

    api_base_url = st.sidebar.text_input(
        "API base URL",
        value=DEFAULT_API_BASE_URL,
    )

    st.sidebar.markdown("### Start backend first")
    st.sidebar.code(
        "python ingest.py\n"
        "python -m rag.index\n"
        "uvicorn api.main:app --reload"
    )

    tabs = st.tabs(
        [
            "Health",
            "List Titles",
            "Title by ID",
            "Stats",
            "Ask",
        ]
    )

    with tabs[0]:
        show_health(api_base_url)

    with tabs[1]:
        show_titles(api_base_url)

    with tabs[2]:
        show_title_by_id(api_base_url)

    with tabs[3]:
        show_stats(api_base_url)

    with tabs[4]:
        show_ask(api_base_url)


if __name__ == "__main__":
    main()

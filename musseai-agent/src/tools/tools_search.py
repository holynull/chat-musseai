from langchain_core.tools import tool
from openai_assistant_tools import GoogleSerperAPIWrapper
from loggers import logger
import traceback


@tool
def search_webpage(terms: str) -> str:
    """Performs a web search using Google search engine and returns formatted results.

    This function executes a search through GoogleSerperAPI and handles multiple types
    of search results including news, organic search results, images, and places.
    All results are formatted into a unified structure before being returned.

    Args:
        terms (str): The search query terms to be used for Google search

    Returns:
        str: A JSON string containing search results in the following format:
            {
                "search_result": [
                    {
                        "title": "Result title",
                        "link": "Result URL link",
                        "imageUrl": "Related image URL (if available)"
                    },
                    ...
                ]
            }

    Notes:
        - Returns "There is no result return." if no results are found
        - Result types can be news, organic search, images, or places
        - Each result item will contain a title and may include link and imageUrl
        - The function processes all result types uniformly for consistent output
    """
    try:
        newsSearch = GoogleSerperAPIWrapper(type="search")
        results = newsSearch.results(terms)
        if "news" in results:
            results = results["news"]
        elif "organic" in results:
            results = results["organic"]
        elif "images" in results:
            results = results["images"]
        elif "places" in results:
            results = results["places"]
        else:
            return "There is no result return."
        search_result = [
            {
                "title": r["title"],
                "link": r["link"] if "link" in r else "",
                "snippet": r["snippet"] if "snippet" in r else "",
                "imageUrl": r["imageUrl"] if "imageUrl" in r else "",
            }
            for r in results
        ]
        return {"search_result": search_result}
    except Exception as e:
        logger.error(traceback.format_exc())
        return e


@tool
def search_news(terms: str, tbs: str) -> str:
    """Performs a news search using Google News and returns formatted results in JSON format.
    This function executes a news search through GoogleSerperAPI's news search feature. It processes
    and formats various types of search results into a unified structure.

    Args:
        terms (str): The search query terms to be used for news search
        tbs (str): Time-based search parameter to filter news by date (e.g., 'qdr:d' for past 24 hours)

    Returns:
        str: A JSON string containing search results in the following format:
            {
                "search_result": [
                    {
                        "title": "News article title",
                        "link": "Article URL",
                        "snippet": "Article snippet or description",
                        "imageUrl": "Related image URL (if available)"
                    },
                    ...
                ]
            }

    Notes:
        - Returns "There is no result return." if no results are found
        - Results can include different types (news, organic, images, places)
        - Each result contains title and snippet, may include link and imageUrl
        - After executing this tool, you should execute `summarizeRelevantContentsNews`
        - The returned JSON string can be parsed to access structured data
    """
    try:
        newsSearch = GoogleSerperAPIWrapper(type="news", tbs=tbs)
        results = newsSearch.results(query=terms)

        if "news" in results:
            results = results["news"]
        elif "organic" in results:
            results = results["organic"]
        elif "images" in results:
            results = results["images"]
        elif "places" in results:
            results = results["places"]
        else:
            return "There is no result return."
        search_result = [
            {
                "title": r["title"],
                "link": r["link"] if "link" in r else "",
                "snippet": r["snippet"],
                "imageUrl": r["imageUrl"] if "imageUrl" in r else "",
            }
            for r in results
        ]
        return {"search_result": search_result}
    except Exception as e:
        logger.error(traceback.format_exc())
        return e


@tool
def search_place(terms: str) -> str:
    """Performs a place search using Google Places API and returns raw search results.

    This function executes a place search through GoogleSerperAPI's places search feature
    and returns the raw search results without additional formatting.

    Args:
        terms (str): The search query terms to be used for place search

    Returns:
        str: Raw search results from the API. The results could contain different types
        of data (news, organic, images, places) depending on the search results.
        Returns "There is no result return." if no results are found.

    Notes:
        - The function returns raw API results unlike other search functions
        - Results may contain various types of data based on API response
        - Useful for location-based searches and place information retrieval
        - Can be used to find businesses, landmarks, and other physical locations
    """
    try:
        newsSearch = GoogleSerperAPIWrapper(type="places")
        results = newsSearch.results(query=terms)
        if "news" in results:
            results = results["news"]
        elif "organic" in results:
            results = results["organic"]
        elif "images" in results:
            results = results["images"]
        elif "places" in results:
            results = results["places"]
        else:
            return "There is no result return."
        return results
    except Exception as e:
        logger.error(traceback.format_exc())
        return e


@tool
def search_image(terms: str) -> str:
    """Performs an image search using Google Images and returns raw search results.

    This function executes an image search through GoogleSerperAPI's image search feature
    and returns the raw search results without additional formatting.

    Args:
        terms (str): The search query terms to be used for image search

    Returns:
        str: Raw search results from the API. The results could contain different types
        of data (news, organic, images, places) depending on the search results.
        Returns "There is no result return." if no results are found.

    Notes:
        - The function returns raw API results unlike other search functions
        - Results may contain various types of data based on API response
        - Particularly useful for finding images related to search terms
        - Results typically include image URLs and related metadata
    """
    try:
        newsSearch = GoogleSerperAPIWrapper(type="images")
        results = newsSearch.results(query=terms)
        if "news" in results:
            results = results["news"]
        elif "organic" in results:
            results = results["organic"]
        elif "images" in results:
            results = results["images"]
        elif "places" in results:
            results = results["places"]
        else:
            return "There is no result return."
        return results
    except Exception as e:
        logger.error(traceback.format_exc())
        return e


@tool
def access_links_content(links: list[dict]):
    """Access the links content.
    Args:
        list: A list containing data in the following format:
        [
            {
                "title": "News article title",
                "link": "Article URL",
                "snippet": "Article snippet or description",
                "imageUrl": "Related image URL (if available)"
            },
            ...
        ]
    """
    return {"search_result": [{"link": link} for link in links]}


tools = [search_webpage, search_news, search_image, search_place]

try:
    import weasyprint
    print("WeasyPrint imported.")
    print(f"Version: {getattr(weasyprint, '__version__', 'unknown')}")
    if hasattr(weasyprint, 'default_url_fetcher'):
        print("Found weasyprint.default_url_fetcher")
    else:
        print("weasyprint.default_url_fetcher NOT found")
        
    try:
        from weasyprint import default_url_fetcher
        print("Success: from weasyprint import default_url_fetcher")
    except ImportError as e:
        print(f"Fail: from weasyprint import default_url_fetcher -> {e}")

except ImportError:
    print("WeasyPrint not installed.")

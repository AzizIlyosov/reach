# -*- coding: utf-8 -*-

# Scrapy settings for wsf_scraping project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#     http://scrapy.readthedocs.org/en/latest/topics/downloader-middleware.html
#     http://scrapy.readthedocs.org/en/latest/topics/spider-middleware.html

BOT_NAME = 'wsf_scraper'

SPIDER_MODULES = ['wsf_scraping.spiders']
NEWSPIDER_MODULE = 'wsf_scraping.spiders'
# LOG_ENABLED = False
LOG_LEVEL = 'INFO'

# Force UTF-8 encoding
FEED_EXPORT_ENCODING = 'utf-8'

# Crawl responsibly by identifying yourself (and your website)
# USER_AGENT = 'wsf_scraping (+wateystrdjytkfu)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 64

# Disable cookies (enabled by default)
COOKIES_ENABLED = False

#  who_iris and who_iris_single_page per-page results
WHO_IRIS_RPP = 250

DUPEFILTER_CLASS = "wsf_scraping.filter.BLOOMDupeFilter"

FEED_URI = './results/scrap_result.json'
FEED_FORMAT = 'json'
FEED_EXPORT_ENCODING = 'utf-8'

# Lists to look for (case insensitive)
SEARCH_FOR_LISTS = ['references', 'bibliography', 'citations']

# Keywords to look for (case insensitive)
SEARCH_FOR_KEYWORDS = ['wellcome']

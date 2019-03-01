# -*- coding: utf-8 -*-
import logging
from urllib.parse import urlparse
from scrapy.utils.project import get_project_settings
from .storage import S3Storage, LocalStorage, get_file_hash
from scrapy.exceptions import DropItem


class WsfScrapingPipeline(object):
    def __init__(self, organisation):
        """Initialise the pipeline, giving it access to the settings, keywords
           and creating the folder in which to store pdfs if stored locally.
        """

        self.settings = get_project_settings()
        uri = self.settings['FEED_URI'].replace('%(name)s', organisation)
        self.setup_storage(uri, organisation)
        self.manifest = self.storage.get_manifest()

        # Initialize logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info(
            'Pipeline initialized FEED_CONFIG=%s',
            self.settings.get('FEED_CONFIG'),
        )

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.spider.name)

    def setup_storage(self, url, organisation):
        """Take the output url and set the right feed storage for the pdf.

        Sets the storage system in use for the pipeline in the following:
          * S3Storage: Store the pdfs in Amazon S3.
          * LocalStorage: Store the pdfs in a local directory.

        Args:
            - url: A string reprensenting the location to store the pdf files.
        """
        parsed_url = urlparse(url)
        scheme = parsed_url.scheme
        if scheme == 's3':
            self.storage = S3Storage(parsed_url.path, organisation)
        else:
            self.storage = LocalStorage(parsed_url.path, organisation)

    def is_in_manifest(self, hash):
        """Check if a file hash is in the current manifest.

        Args:
            - hash: A 36 chars string repsenting the md5 digest of a file.
        Returns:
            - True if the file hash is in the manifest, else False.
        """
        if hash[:2] in self.manifest.keys():
            if hash in self.manifest[hash[:2]]:
                return True
        return False

    def process_item(self, item, spider):
        """Process items sent by the spider.

        Args:
            - item: The item returned by the spider.
            - spider: The spider from which the item id coming.
        Raises:
            - DropItem: If the pdf couldn't be saved, we want to drop the item.
        Returns:
            - item: The processed item, to be used in a feed storage.
        """

        if not item['pdf']:
            raise DropItem(
                'Empty filename, could not parse the pdf.'
            )
        item['hash'] = get_file_hash(item['pdf'])

        scraped = self.is_in_manifest(item['hash'])

        if not scraped:
            self.storage.save(item['pdf'], item['hash'])
        else:
            raise DropItem(
                'This pdf is already in the manifest file.'
            )

        return item

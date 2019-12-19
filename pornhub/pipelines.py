# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import os
import sys
import time

import requests
import scrapy
from scrapy.pipelines.files import FilesPipeline

from pornhub.items import PornhubItem
from pornhub.spiders.all_channel import AllChannel


class PornhubPipeline(object):

    def process_item(self, item, spider: AllChannel):
        if isinstance(item, PornhubItem):
            file_path = spider.settings.get('ARIA_PATH_PREFIX') + '/' + spider.settings.get(
                'FILES_STORE') + '/' + item.get('file_channel')
            file_name = item.get('file_name') + '.mp4'
            # check file name contains file separator like \ or /
            if os.sep in file_name:
                file_name = file_name.replace(os.sep, '|')
            base_url = 'http://127.0.0.1:8800/jsonrpc'
            token = 'token:' + spider.settings.get('ARIA_TOKEN')
            aria_data = {
                'jsonrpc': '2.0',
                'method': 'aria2.addUri',
                'id': '0',
                'params': [token, [item['file_urls']], {'out': file_name, 'dir': file_path}]
            }
            spider.logger.info('send to aria2 rpc, args %s', aria_data)
            response = requests.post(url=base_url, json=aria_data)
            gid = response.json().get('result')

            retry_times = 0
            while True:
                if retry_times > spider.settings.get('RETRY_TIMES'):
                    spider.logger.error('over retry times, [%s] download fail', file_name)
                    break
                time.sleep(5)
                status_data = {
                    'jsonrpc': '2.0',
                    'method': 'aria2.tellStatus',
                    'id': '0',
                    'params': [token, gid, ['status']]
                }
                status_resp = requests.post(url=base_url, json=status_data)
                status = status_resp.json().get('result').get('status')
                if status == 'error':
                    spider.logger.info('download error, remove and retry')
                    remove_data = {
                        'jsonrpc': '2.0',
                        'method': 'aria2.removeDownloadResult',
                        'id': '0',
                        'params': [token, gid]
                    }
                    requests.post(url=base_url, json=remove_data)
                    retry_resp = requests.post(url=base_url, json=aria_data)
                    gid = retry_resp.json().get('result')
                    retry_times += 1
                elif status == 'complete':
                    break


class DownloadVideoPipeline(FilesPipeline):

    def get_media_requests(self, item, info):
        if isinstance(item, PornhubItem):
            info.spider.logger.info('接到下载任务，文件名：{0}\n地址：{1}\n'.format(item['file_name'] + '.mp4', item['file_urls']))
            return scrapy.Request(url=item['file_urls'], meta=item)

    def file_path(self, request, response=None, info=None):
        down_name = request.meta['file_channel'] + '/' + request.meta['file_name'] + '.mp4'
        return down_name

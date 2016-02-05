import praw
import time
import datetime
import re
import os
import urllib
import requests
import json
from goog import getQuotes
from collections import OrderedDict
import OAuth2Util

###### CONFIG VARS
DEVELOPER = False
SUBREDDIT = "investing+InvestmentClub"
MAX_QUOTES = 10

###### STATIC VARS
__author__ = 'spookyyz'
__version__ = '1.0'
user_agent = 'Stock Quotr {} by {}'.format(__version__,__author__)
REDDIT = praw.Reddit(user_agent=user_agent)
o = OAuth2Util.OAuth2Util(REDDIT, print_log=True)

###### SETUP VARS
cache = []
ticker_symbols = []
symbol = ""
START_TIME = time.time()
company_list = []

def scanComments():
    """
    Will scan comments in the globally defined SUBREDDIT and return only unresponded to previously,
    new comments containing a symbol in the format of $SYMBOL (case sense)
    """
    sub_to_scan = 'spookyyz' if DEVELOPER else SUBREDDIT
    sub_object = REDDIT.get_subreddit(sub_to_scan)
    if DEVELOPER: print "Scanning [{}]".format(sub_to_scan)
    for comment in sub_object.get_comments(limit=50):
        post_text = ''
        ticker_symbols = []
        comment_text = comment.body
        pattern = re.compile('\$[A-Z]{1,5}')
        comment_utcunix = datetime.datetime.utcfromtimestamp(comment.created) - datetime.timedelta(hours=8) #offset from comment time as seen by the server to UTC
        start_utcunix = datetime.datetime.utcfromtimestamp(START_TIME)
        if (comment.id not in cache and comment_utcunix > start_utcunix or DEVELOPER): #ignore previously grabbed comments
            for symbol in re.findall(pattern, comment_text): #check for symbol against regex in comment text for non-cached comments
                if (symbol[1:] == "X" and not 'steel' in comment_text.lower()): #skipping comments containing only "$X" as symbol with no mention of steel (X symbol is a steel stock) as many people post "if you have $X dollars"
                    continue
                if (symbol[-1:] == '.'): #trim a trialing (period) on a ticker symbol
                    symbol = symbol[:-1]

                ticker_symbols.append(symbol[1:])
                ticker_symbols = list(OrderedDict.fromkeys(ticker_symbols))

            if (ticker_symbols):
                if DEVELOPER: print "Passing these symbols to getData:", ticker_symbols, "from:", comment.id
                post_text = getData(ticker_symbols, comment.id)
                if (post_text):
                    try:
                        print "Replying to {} with symbols:{}".format(comment.id, ticker_symbols)
                        if DEVELOPER:
                            print "\n\n####POST TEXT####\n\n", post_text
                        else:
                            comment.reply(post_text)
                        cache.append(comment.id)
                        time.sleep(15)
                    except Exception, e:
                        print "[ERROR@post]:", str(e)
                        time.sleep(15)
                else:
                    cache.append(comment.id)
                    continue



            del ticker_symbols[:]


def getData(symbols, comment_id):
    """
    Method to lookup stock information within Yahoo's YQL database and Google's API for current price.
    Input: List of symbol(s), Output: YQL/Google requested data dict
    """
    symbols_string = ','.join(symbols)
    url = "https://query.yahooapis.com/v1/public/yql"
    query = 'select Name, symbol, EarningsShare, MarketCapitalization, PERatio from yahoo.finance.quotes where symbol in ("{}")'.format(symbols_string)
    payload = {'q' : query, 'diagnostics' : 'false', 'env' : 'store://datatables.org/alltableswithkeys', 'format' : 'json'}
    if DEVELOPER: print "Beginning Yahoo Lookup for: ", symbols
    try:
        r = requests.get(url, params=payload)
    except Exception, e:
        print "YAHOO LOOKUP ERROR: " + str(e)
        cache.append(comment_id)
        return False
    json_response = json.loads(r.text)
    #print json.dumps(json_response, indent=1)
    json_quote = json_response["query"]["results"]["quote"]
    quote_count = 0
    if DEVELOPER: print json.dumps(json_response, indent=2)

    company_data = {}
    company_list = []
    if len(symbols) > 1:
        for item in json_quote:
            company_data = {}
            try:
                company_name = item['Name']
            except:
                company_name = json_quote['Name']

            if company_name is None:
                print "REMOVED:", symbols[quote_count]
                del symbols[quote_count]
                continue
            quote_count += 1
            company_data['Name'] = '[' + str(item['Name']) + ']' + '(http://finance.yahoo.com/q?s=' + str(item['symbol']) + ')'
            company_data['EPS'] = str(item['EarningsShare'])
            company_data['MarketCap'] = str(item['MarketCapitalization'])
            company_data['PERatio'] = str(item['PERatio'])
            company_data['Symbol'] = str(item['symbol'])
            company_list.append(company_data)
    else:
        company_data['Name'] = '[' + str(json_quote['Name']) + ']' + '(http://finance.yahoo.com/q?s=' + str(json_quote['symbol']) + ')'
        company_data['EPS'] = str(json_quote['EarningsShare'])
        company_data['MarketCap'] = str(json_quote['MarketCapitalization'])
        company_data['PERatio'] = str(json_quote['PERatio'])
        company_data['Symbol'] = str(json_quote['symbol'])
        company_list.append(company_data)

    if (symbols):
        data_g = getQuotes(symbols)
        for idx, info in enumerate(data_g): #gathering google data
            company_list[idx]['Price'] = info['LastTradePrice']
            company_list[idx]['Change'] = info['Change']
            company_list[idx]['ChangePercentage'] = info['ChangePercentage']
            company_list[idx]['LastTrade'] = info['LastTradeDateTimeLong']

        if DEVELOPER: print company_list
        post_text = '|Company|Symbol|Price|Change|Change%|Analytics|\n'
        post_text += '|:--|:--|:--|:--|:--|:--|\n'
        for company in company_list[:MAX_QUOTES]:
            post_text += ('|' + company['Name'] + '|' + company['Symbol'] + '|' + company['Price'] + '|' + company['Change'] + '|' + company['ChangePercentage'] + '| [HOVER: More Info](/s "' + 'MarketCap: ' +
            company['MarketCap'] + ' \ EPS: ' + company['EPS'] + ' \ P/E Ratio: ' + company['PERatio'] + ' \ Last Report: ' + company['LastTrade'] + '")\n')
        post_text += '\n^^_Quotr ^^Bot ^^v{} ^^by ^^[spookyyz](https://www.reddit.com/message/compose/?to=spookyyz&subject=Quotr%20Bot)_'.format(__version__)
        del company_list[:]
        return post_text
    else:
        del company_list[:]
        cache.append(comment_id)
        return False


while True:
    scanComments()
    print "Sleeping 20...", cache
    time.sleep(20)

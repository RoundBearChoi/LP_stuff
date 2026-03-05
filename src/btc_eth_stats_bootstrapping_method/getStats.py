import time
from priceData import download_crypto_daily_closing
from getPriceRatio import get_price_ratio 
from getPriceChange import get_price_change
from sortPriceChange import sort_price_change
from drawGraphOnHistoricPrice import draw_graph
from generateReplicates import generate_replicates
from sortReplicates import sort_reps
from getUpperLower import get_upper_lower
from sortSummary import sort_upper_lower
from drawGraphOnReplicates import draw 


def get_stats(asset1: str, asset2: str) -> None:
    print('')
    print('lets go baby..')

    download_crypto_daily_closing(crypto_symbol=asset1, years=1)
    time.sleep(1)
    download_crypto_daily_closing(crypto_symbol=asset2, years=1)

    get_price_ratio(asset1, asset2)

    get_price_change(asset1, asset2)
    
    sort_price_change(asset1, asset2)

    draw_graph(asset1, asset2)

    generate_replicates(asset1, asset2, 100)

    sort_reps(asset1, asset2)

    get_upper_lower(asset1, asset2)

    sort_upper_lower(asset1, asset2)

    draw(asset1, asset2)


if __name__ == '__main__':
    get_stats('btc', 'eth')

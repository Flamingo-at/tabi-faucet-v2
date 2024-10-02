import time
import asyncio
import datetime

from web3.auto import w3
from loguru import logger
from aiohttp import ClientSession
from eth_account.messages import encode_defunct
from pyuseragents import random as random_useragent

from config import *


logger.add('logger.log', format='{time:YYYY-MM-DD | HH:mm:ss.SSS} | {level} \t| {function}:{line} - {message}')


def create_signature(private_key: str, text):
    message = encode_defunct(text=text)
    signed_message = w3.eth.account.sign_message(message, private_key)
    return signed_message.signature.hex()


async def worker():
    while not q.empty():
        try:
            private_key = await q.get()
            address = w3.eth.account.from_key(private_key).address

            async with ClientSession(
                headers={
                    'User-Agent': random_useragent(),
                }
            ) as client:

                timestamp = int(time.time()) * 1_000_000
                text = f'Hi! Welcome to TabiChain.\n\nPlease sign the message to let us know that you own the wallet.\n\nSigning is gas-less and will not give TabiChain permission to conduct any transactions with your wallet.\n\nTime stamp is {timestamp}.'
                signature = create_signature(private_key, text)

                logger.info(f'{address} | Login')
                response = await client.post('https://api.tabibot.com/api/iam/v1/eth_login',
                                             json={
                                                 'address': address,
                                                 'signature': signature,
                                                 'timestamp': timestamp
                                             })
                data = await response.json()
                if data['code'] != 200:
                    raise Exception(f'Error login | {data}')

                access_token = data['data']['token']

                client.headers.update({
                    'Auth-Testnet': 'true',
                    'Authorization': access_token
                })

                response = await client.post('https://api.tabibot.com/api/testnet/activity/faucet/claim')
                data = await response.json()
                if data['code'] != 200:
                    logger.error(f'{address} | Error Claim | {data}')
                else:
                    logger.info(f'{address} | Successfully Claim | {data["data"]}')

        except Exception as error:
            logger.error(f'{address} | {error}')


async def check_status_faucet():
    try:
        async with ClientSession(
            headers={
                'User-Agent': random_useragent(),
            }
        ) as client:

            response = await client.get('https://api.tabibot.com/api/testnet/activity/token/status')
            data = await response.json()
            if data['data']['claimed_total_val'] >= data['data']['total_token_num']:
                duration = data['data']['next_refresh_time']/1_000_000 - int(time.time())
                next_open_faucet  = datetime.timedelta(seconds=duration)
                logger.info(f'Faucet will open in {next_open_faucet}')
                return False
            return True

    except Exception as error:
        logger.error(error)


async def main():
    if await check_status_faucet():
        tasks = [asyncio.create_task(worker()) for _ in range(THREADS)]
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    print('Bot Tabi Faucet "Testnet V2 Carnival" @flamingoat\n')

    with open('private_key.txt', 'r') as file:
        private_keys = file.read().splitlines()

    q = asyncio.Queue()

    for private_key in private_keys:
        q.put_nowait(private_key)

    asyncio.run(main())

    logger.debug('Press Enter to exit...')
    input()

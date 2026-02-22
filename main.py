# -*- coding: utf-8 -*-
"""
Opium - Main Entry Point

Запуск:
    python main.py              # API сервер на 0.0.0.0:8000
    python main.py --port 3000  # API на порту 3000
    python main.py --debug      # Debug режим
"""

import argparse
import logging
import sys

import uvicorn

from core.logging import setup_logging

# Настраиваем логирование ДО всех импортов
setup_logging(console_level="DEBUG", file_level="DEBUG")


def main():
    parser = argparse.ArgumentParser(
        description="opium - funpay automation",
    )
    parser.add_argument("--host", default="0.0.0.0", help="host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="port (default: 8000)")
    parser.add_argument("--debug", action="store_true", help="debug mode")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    print(f"""
             ..                                      
            ..;:.                                    
           .;$&$;..                                  
          .:$$Xx$:.                                  
          .X$;..:x..                 ...             
        ...$x...:X:.         ...    ..:..  ...       
          .x;...X$:.        ...:.. ..::.. ......     
          .++..x$X.   .........::...::::..:::........
...........;x;$&$;:::::::......::::::.:::::::........
.....   ...;$&$$:..    ..::....::::::::::::::....::..
      ...;$&&$+..        ...::::+XXXXxxxxx+;:::::....
.......;$&&$X+..............::::+$$xx+;++xx+::::.....
......x$&$+.:+.............:::::+$X++;;;:xX+:::::....
   ..$&&x:...+:.....  ..::::::::x$Xx++;;;xX+::::::::.
   .x&$x...;$&&$&&X:..::::::::::x$X+;xX;;xX+::::.....
::::X&X...$&$X$xX$$&+.......:::::XXx+XX++xx:::::.... 
 ..:$&+..+$+..+;..;$&. ....:::::::+X$$$$X+:::::::....
  ..X&;..+$:..:x...x$....:::::.::::::::::::::........
::..;&X:..+X:..X...xx..........::::.::::.::::..      
.....;$X;......;x.+X:.       ..:.....::.....:..      
      .:X&X;:::+$X:..................::::::::::::::::
....::::::::::::+;......................        
....   .......  :+.                                  
      ..;X$$x:...+..                                 
      .:X$$$$+...x..                                 
      ..x$$$x...x:.                                  
        .:X$xxXx..                                   
           ...                
            ..                                  

          
opium
backend

          
api:  http://{args.host}:{args.port}
docs: http://{args.host}:{args.port}/docs

""")

    try:
        uvicorn.run("api.main:app", host=args.host, port=args.port, log_level="info")
    except KeyboardInterrupt:
        print("\n\nостановлено")
    except Exception as e:
        logging.error(f"fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

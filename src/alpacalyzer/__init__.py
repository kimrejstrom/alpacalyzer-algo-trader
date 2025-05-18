# Add this to your __init__ or at the start of your script
import tqdm

tqdm.tqdm = lambda *args, **kwargs: args[0]  #

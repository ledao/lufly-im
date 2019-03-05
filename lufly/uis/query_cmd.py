from lufly.engine.search_sys import Searcher


if __name__ == "__main__":
    searcher = Searcher() 
    while(True):
        q = input(">:")
        if q == "q" or q == "Q":
            break
        if q == '':
            continue
        result = []
        result.extend(searcher.query_char_phones(q))
        result.extend(searcher.query_char_phone_shapes(q))
        result.extend(searcher.query_word_phones(q))
        result.extend(searcher.query_word_phone_shapes(q))

        fresult = list(filter(lambda e: e.phones == q, result))
        if len(fresult) > 0:
            for r in fresult:
                print(r)
        else:
            for r in result:
                print(r)
        
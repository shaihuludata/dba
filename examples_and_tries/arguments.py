import sys


def main(wtf):
    print(wtf)


if __name__ == '__main__':
    a = len(sys.argv)
    # if len(sys.argv[1]) > 0:
    #     main(sys.argv[1])
    # else:
    #     main(123)
    main(a)

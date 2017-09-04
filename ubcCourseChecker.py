from http.cookiejar import CookieJar

from urllib.request import HTTPCookieProcessor, build_opener, install_opener, Request, urlopen
from urllib.parse import urlencode
from enum import Enum, auto

import json
import re
import time

from random import randrange


# Notify that a course is available
def sendEmail(seatType, data):
    import smtplib

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(data['sourceEmailAddress'], data['sourceEmailPassword'])

    msg = "Subject: Registered for course!\n Got you into %s" % seatType
    server.sendmail(data['sourceEmailAddress'], data['destEmailAddress'], msg)


def notify(seatType, dataDict):
    print("Seat available.")
    print(seatType)
    sendEmail(seatType, dataDict)


# Delay to prevent sending too many requests
def wait(delay):
    randDelay = delay + int(randrange(11))
    time.sleep(randDelay)


# Automatically registers in the course
def autoRegister(cwl_user, cwl_pass, registerURL):
    # Cookie / Opener holder
    cj = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cj))

    # Login Header
    opener.addheaders = [('User-agent', 'UBC-Login')]

    # Install opener
    install_opener(opener)

    # Form POST URL
    postURL = "https://cas.id.ubc.ca/ubc-cas/login/"

    # First request form data
    formData = {
        'username': cwl_user,
        'password': cwl_pass,
        'execution': 'e1s1',
        '_eventId': 'submit',
        'lt': 'xxxxxx',
        'submit': 'Continue >'
    }

    # Encode form data
    data = urlencode(formData).encode('UTF-8')

    # First request object
    req = Request(postURL, data)

    # Submit request and read data
    resp = urlopen(req)
    respRead = resp.read().decode('utf-8')

    # Find the ticket number
    ticket = "<input type=\"hidden\" name=\"lt\" value=\"(.*?)\" />"
    t = re.search(ticket, respRead)

    # Extract jsession ID
    firstRequestInfo = str(resp.info())
    jsession = "Set-Cookie: JSESSIONID=(.*?);"
    j = re.search(jsession, firstRequestInfo)

    # Second request form data with ticket
    formData2 = {
        'username': cwl_user,
        'password': cwl_pass,
        'execution': 'e1s1',
        '_eventId': 'submit',
        'lt': t.group(1),
        'submit': 'Continue >'
    }

    # Form POST URL with JSESSION ID
    postURL2 = "https://cas.id.ubc.ca/ubc-cas/login;jsessionid=" + j.group(1)

    # Encode form data
    data2 = urlencode(formData2).encode('UTF-8')

    # Submit request
    req2 = Request(postURL2, data2)
    resp2 = urlopen(req2)

    loginURL = "https://courses.students.ubc.ca/cs/secure/login"
    # Perform login and registration
    urlopen(loginURL)
    register = urlopen(registerURL)
    respReg = register.read()
    print("Course Registered.")


class seatStatus(Enum):
    NONE_AVAILABLE = auto()
    GENERAL_AVAILABLE = auto()
    RESTRICTED_AVAILABLE = auto()


# Scan webpage for seats
def checkSeats(varCourse):
    url = varCourse
    ubcResp = urlopen(url)
    ubcPage = ubcResp.read().decode('utf-8')

    # Search pattern (compiled for efficiency)
    totalSeats = re.compile(
        "<td width=&#39;200px&#39;>Total Seats Remaining:</td>" + "<td align=&#39;left&#39;><strong>(.*?)</strong></td>")
    generalSeats = re.compile(
        "<td width=&#39;200px&#39;>General Seats Remaining:</td>" + "<td align=&#39;left&#39;><strong>(.*?)</strong></td>")
    restrictedSeats = re.compile(
        "<td width=&#39;200px&#39;>Restricted Seats Remaining\*:</td>" + "<td align=&#39;left&#39;><strong>(.*?)</strong></td>")

    # Search for the seat number element
    t = re.search(totalSeats, ubcPage)
    g = re.search(generalSeats, ubcPage)
    r = re.search(restrictedSeats, ubcPage)

    # Find remaining seats
    if t and t.group(1) == '0':
        return seatStatus.NONE_AVAILABLE
    else:
        print("Error: Can't locate total number of seats.")

    if g and g.group(1) != '0':
        return seatStatus.GENERAL_AVAILABLE
    else:
        print("Error: Can't locate number of general seats.")

    if r and r.group(1) != '0':
        return seatStatus.RESTRICTED_AVAILABLE
    else:
        print("Error: Can't locate number of restricted seats.")


def getDataFromFile():
    return json.load(open('ubc-coursecheckConfig.json', 'r'))


def saveDataToFile(dataDict):
    if dataDict['saveConfig'] == "y":
        fileToWrite = open('ubc-coursecheckConfig.json', 'w')
        json.dump(dataDict, fileToWrite)


def getDataFromUser():
    data = {}
    data['courseURL'] = input("Enter course + section link:")

    season = input("Summer course (y/n):")
    if season == 'y':
        data['season'] = 'S'
    else:
        data['season'] = 'W'

    data['year'] = input("Term year (2017/2018/...):")
    data['acceptRestricted'] = input("Allowed restricted seating? (y/n):")

    delay = int(input("Check every _ seconds?:"))
    # Prevent too fast of a search rate/DOSing the website
    if delay < 15:
        data['delay'] = 15

    data['register'] = input("Autoregister when course available? (y/n):")
    if data['register'] == "y":
        data['cwl_user'] = input("CWL Username:")
        data['cwl_pass'] = input("CWL Password:")

    data['emailNotification'] = input("Send email notification? (y/n):")
    if data['emailNotification'] == 'y':
        data['sourceEmailAddress'] = input("Source email address:")
        data['sourceEmailPassword'] = input("Source email password:")
        data['destEmailAddress'] = input("Destination email address:")

    data['saveConfig'] = input("Save settings to config file? (y/n):")

    return data


def acquireData():
    resume = input("Load settings from config file? (y/n):")
    if resume == "y":
        data = getDataFromFile()
    else:
        data = getDataFromUser()
    return data


def main():
    # Get course parameters
    data = acquireData()
    saveDataToFile(data)  # only saves if flag is on

    # Extract department, course #, and section #
    deptPattern = 'dept=(.*?)&'
    coursePattern = 'course=(.*?)&'
    sectionPattern = 'section=(.*)'
    dept = re.search(deptPattern, data['courseURL'])
    course = re.search(coursePattern, data['courseURL'])
    sect = re.search(sectionPattern, data['courseURL'])

    registerURL = 'https://courses.students.ubc.ca/cs/main?sessyr=' + data['year'] + '&sesscd=' + data[
        'season'] + '&pname=subjarea&tname=subjareas&submit=Register%20Selected&wldel=' + dept.group(
        1) + '|' + course.group(1) + '|' + sect.group(1)
    courseURL = 'https://courses.students.ubc.ca/cs/main?sessyr=' + data['year'] + '&sesscd=' + data[
        'season'] + '&pname=subjarea&tname=subjareas&req=5&dept=' + dept.group(
        1) + '&course=' + course.group(1) + '&section=' + sect.group(1)

    print("Checking for seat availability...")

    # Conditional for determining whether to register/notify
    while True:
        status = checkSeats(courseURL)

        if data['register'] == 'y' and ((status == seatStatus.GENERAL_AVAILABLE) or (
                        status == seatStatus.RESTRICTED_AVAILABLE and data['acceptRestricted'] == "y")):
            autoRegister(data['cwl_user'], data['cwl_pass'], registerURL)
            notify(status, data)
            break
        elif data['register'] == 'n' and ((status == seatStatus.GENERAL_AVAILABLE) or (
                        status == seatStatus.RESTRICTED_AVAILABLE and data['acceptRestricted'] == "y")):
            notify(status, data)
            continue
        else:
            wait(data['delay'])

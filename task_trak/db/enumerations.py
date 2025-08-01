from enum import Enum

# enumerations
class e_UserType(Enum):
    SysAdm = ("SysAdm", 1)
    Admin = ("Admin", 2)
    Staff = ("Staff", 3)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_Gender(Enum):
    Male = ("Male", 1)
    Female = ("Female", 2)
    Other = ("Other", 3)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_Priority(Enum):
    Low = ("Low", 1)
    Medium = ("Medium", 2)
    High = ("High", 3)
    
    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_ProjStatus(Enum):
    Pending = ("Pending", 1)
    Inprocess = ("In Process", 2)
    PendReview = ("Pending Review", 3)
    Done = ("Done", 4)
    Cancelled = ("Cancelled", 5)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_TaskStatus(Enum):
    Pending = ("Pending", 1)
    Inprocess = ("In Process", 2)
    PendReview = ("Pending Review", 3)
    Done = ("Done", 4)
    Cancelled = ("Cancelled", 5)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_SubTaskStatus(Enum):
    Pending = ("Pending", 1)
    Done = ("Done", 2)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_SentVia(Enum):
    SysNotif = ("System Notification", 1)
    EMail = ("Email Notification", 2)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_CommCntrStatus(Enum):
    Pending = ("Pending", 1)
    Read = ("Read", 2)
    
    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_TranType(Enum):
    Company = ("Company", 1)
    Staff = ("Staff", 2)
    ProjectTmpl = ("Project Template", 3)
    TaskTmpl = ("Task Template", 4)
    SubTaskTmpl = ("SubTask Template", 5)
    ProjectTran = ("Project Transaction", 6)
    TaskTran = ("Task Transaction", 7)
    SubTaskTran = ("SubTask Transaction", 8)
    CommCntr = ("Coomunication Center", 9)
    Attachment = ("Attachment", 10)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_ActionType(Enum):
    LogInSuccess = ("LogInSuccess", 'Log-In Successful') #LoginSuccess will be in database's action type and log-in successful will be on the action description in the database
    LogInFailure = ("LogInFailure", 'Log-In Failed') #dynamic - append values to the end in controller
    LogOut = ("LogOut", 'Log-Out')
    AddRecord = ("AddRecord", 'Added Record')
    ChangeRecord = ("ChangeRecord", 'Changed Record')
    DeleteRecord = ("DeleteRecord", 'Deleted Record')
    ExportReport = ("ExportReport", 'Exported Report') #dynamic - append values to the end in controller
    PrintReport = ("PrintReport", 'Printed Report') #dynamic - append values to the end in controller

    def __init__(self, idx, textval):
        self.idx = idx
        self.textval = textval

class e_AttachTye(Enum):
    General = ("General", 1)
    DegreeCertificate = ("Degree Certificate", 2)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx

class e_NotificationStatus(Enum):
    Pending = ("Pending", 1)
    Read = ("Read", 2)

    def __init__(self, textval, idx):
        self.textval = textval
        self.idx = idx
        
class e_SysConfig(Enum): #--> Idx, Key, DefVal, Dscr
    AllowAttchExtn = (1, "Allowed File types for attachment", ".bmp, .gif, .jpg, .jpeg, .png, .ico, .mpeg, .pdf, .doc, .docx, .docm, .rtf, .xls, .xlsx, .csv, .txt, .zip, .rar, .7z, .tar, .ppt, .pptx, .mp3, .mp4, .svg, .ttf", "CSV of file extensions allowed as attachement. Ex.: *.doc,.xls,*.pdf")
    MaxAttachSize = (2, "Maximum Attachment Size in MB", 100, "Upto 100 MB size supportable")
    UpcomingDay = (3, "Days for Upcoming Task", 10, "No. of days to condsider for showing upcoming tasks")
    RowsSingleLine = (4, "Rows in Single Line List", 10, "Range: 1 to 50. Ideal 10")
    RowsMultiLine = (5, "Rows in MultiLine List", 10, "Range: 1 to 50. Ideal 10")
    ReportDaysUpto = (6, "Report Days Upto", 90, "Maximum number of days for which reports are generated.")
    UpcomingTaskRepetition = (6, "Upcoming Task Repetition", "1, 2, 3, 5, 7", "Number of days to consider generating system notification for upcoming tasks.")
    OverdueTaskRepetition = (6, "Overdue Task Repetition", "1, 2, 3, 4, 20{3}", "Number of days to consider generating system notification for overdue tasks.")
    DelayedTaskRepetition = (6, "Delayed Task Repetition", "1, 2, 3, 4, 5, 35{7}, 60{10}", "Number of days to consider generating system notification for delayed tasks.")
    Minute = (10, "Minute", "*", "Minute (0 - 59).")
    Hour = (11, "Hour", "*", "Hour (0 - 23).")
    DayOfMonth = (12, "Day of Month", "*", "Day of the month (1 - 31).")
    Month = (13, "Month", "*", "Month (1 - 12).")
    DayOfWeek = (14, "Day of Week", "*", "Day of the week (0 - 7) (Sunday = 0 or 7).")
    
    def __init__(self, Idx, Key, DefVal, Dscr):
        self.Idx = Idx
        self.Key = Key
        self.DefVal = DefVal
        self.Dscr = Dscr

# method to get the enum meber from the value against memeber - useful when retriveing data from db for columns having enum values and what actual value from enum
def get_enum_info_by_idx(enum_class, target_value):
    for member in enum_class:
        if member.value[1] == target_value:
            return member.value
    return None

def get_enum_info_by_textval(enum_class, target_value):
    for member in enum_class:
        if member.value[0] == target_value:
            return member.value
    return None

def enum_to_list(enum_class, user_type=None):
    if enum_class == e_UserType:
        if user_type and e_UserType.SysAdm.textval == user_type:
            return [{member.value[1]: member.value[0]} for member in enum_class]
        return [{member.value[1]: member.value[0]} for member in enum_class if member.value[1] != 1]
    return [{member.value[1]: member.value[0]} for member in enum_class]
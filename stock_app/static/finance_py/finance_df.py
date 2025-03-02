from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By

import time
from datetime import datetime, timedelta
import pandas as pd
import requests
from bs4 import BeautifulSoup
from stock_app.static.finance_py.const import base_url, analysis_url, get_headers

import numpy as np
import scipy.stats as stats
from scipy.stats import gmean, hmean, norm

def exchange_rate(fromdate, todate):
    # Chuyển đổi ngày từ chuỗi sang đối tượng datetime
    start_date = datetime.strptime(fromdate, '%Y-%m-%d')
    end_date = datetime.strptime(todate, '%Y-%m-%d')

    # Tạo một danh sách để lưu trữ DataFrame cho mỗi ngày
    data_frames = []

    # Lặp qua từng ngày trong khoảng thời gian
    while start_date <= end_date:
        date_str = start_date.strftime('%Y-%m-%d')
        url = f"https://www.vietcombank.com.vn/api/exchangerates?date={date_str}"
        response = requests.get(url)
        json_data = response.json().get('Data', [])

        # Nếu không có dữ liệu cho ngày này, bỏ qua
        if not json_data:
            start_date += timedelta(days=1)
            continue

        df_data = pd.DataFrame(json_data)
        df_data['Date'] = date_str  # Thêm cột 'Date' cho mỗi DataFrame
        data_frames.append(df_data)
        

        start_date += timedelta(days=1)

    # Kết hợp tất cả DataFrame thành một DataFrame duy nhất
    df = pd.concat(data_frames, ignore_index=True)
    df = df.drop(columns=['icon'], errors='ignore')  # Bỏ cột 'icon' nếu tồn tại
    df = df.sort_values(by='Date', ascending=False)
    df = df[['Date', 'currencyName', 'currencyCode', 'cash', 'transfer', 'sell']]
    df = df.rename(columns={
        'currencyName':'Currency Name',
        'currencyCode':'Currency Code',
        'cash':'Cash',
        'transfer':'Transfer',
        'sell':'Sell'

    })
    df[['Cash', 'Transfer', 'Sell']] = df[['Cash', 'Transfer', 'Sell']].apply(pd.to_numeric, errors='coerce')
    
    return df

def gold_sjc(fromdate, todate):
    # Chuyển chuỗi ngày sang đối tượng datetime
    fromdate = datetime.strptime(fromdate, '%Y-%m-%d')
    todate = datetime.strptime(todate, '%Y-%m-%d')

    df_list = []

    # URL API
    url = "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx"

    # Duyệt qua từng ngày trong khoảng thời gian
    while fromdate <= todate:
        # Chuyển ngày thành định dạng DD/MM/YYYY
        date_str = fromdate.strftime('%d/%m/%Y')

        # Dữ liệu POST
        data = {
            "method": "GetSJCGoldPriceByDate",
            "toDate": date_str
        }

        # Gửi POST request
        response = requests.post(url, headers=get_headers(), data=data)

        if response.status_code == 200:
            try:
                # Lấy dữ liệu JSON
                data_date = response.json().get('currentDate', date_str)
                data_value = response.json().get('data', [])

                if data_value:
                    # Tạo DataFrame và thêm cột Date
                    df = pd.DataFrame(data_value)
                    df['Date'] = data_date
                    df_list.append(df)
                else:
                    print(f"No data for {date_str}")

            except Exception as e:
                print(f"Error parsing data for {date_str}: {e}")
        else:
            print(f"Error fetching data for {date_str}: {response.status_code}")

        # Tăng ngày thêm 1
        fromdate += timedelta(days=1)

    # Gộp tất cả các DataFrame lại với nhau
    if df_list:
        final_df = pd.concat(df_list, ignore_index=True)
        final_df = final_df[["Id","TypeName","BranchName","BuyValue","SellValue","Date"]]
        final_df = final_df.loc[
            final_df['BranchName'].isin(['Hà Nội', 'Hồ Chí Minh', 'Nha Trang']),
            ['BranchName', 'BuyValue', 'SellValue', 'Date']
        ]
        return final_df
    else:
        return pd.DataFrame()  # Trả về DataFrame rỗng nếu không có dữ liệu

def financial_report(symbol, types, year, timely):

    symbol, types, timely = symbol.upper(), types.upper(), timely.upper()
    year = int(year)

    if types in ['BS', 'BALANCESHEET', 'CDKT']:
        modelType = '1,89,101,411'
    elif types in ['P&L', 'KQKD', 'IC']:
        modelType = '2,90,102,412'
    elif types in ['CF', 'LCTT']:
        modelType = '3,91,103,413'
    else:
        raise ValueError("Invalid types parameter.")

    # Initialize url_y to None
    url_y = None

    if timely in ['YEAR', 'NAM']:
        current_year = datetime.now().year
        years = [current_year - i for i in range(year)]
        fiscal_dates = ','.join([f"{year}-12-31" for year in years])
        url_y = f'https://api-finfo.vndirect.com.vn/v4/financial_statements?q=code:{symbol}~reportType:ANNUAL~modelType:{modelType}~fiscalDate:{fiscal_dates}&sort=fiscalDate&size=2000'

    elif timely in ['QUARTER', 'QUY']:
        current_year = datetime.now().year
        years = [current_year - i for i in range(year)]
        fiscal_dates = []

        for year in years:
            fiscal_dates.extend([f"{year}-03-31", f"{year}-06-30", f"{year}-09-30", f"{year}-12-31"])

        fiscal_dates_str = ','.join(fiscal_dates)
        url_y = f'https://api-finfo.vndirect.com.vn/v4/financial_statements?q=code:{symbol}~reportType:QUARTER~modelType:{modelType}~fiscalDate:{fiscal_dates_str}&sort=fiscalDate&size=2000'

    if url_y is None:
        raise ValueError("Invalid timely parameter.")

    url_ct = f'https://api-finfo.vndirect.com.vn/v4/financial_models?sort=displayOrder:asc&q=codeList:{symbol}~modelType:{modelType}~note:TT199/2014/TT-BTC,TT334/2016/TT-BTC,TT49/2014/TT-NHNN,TT202/2014/TT-BTC~displayLevel:0,1,2,3&size=999'

    response = requests.get(url_y, headers=get_headers())

    df = pd.DataFrame(response.json()['data'])

    pivot_df = df.pivot(index='itemCode', columns='fiscalDate', values='numericValue')
    pivot_df.reset_index(inplace=True)
    pivot_df.columns.name = None

    response_2 = requests.get(url_ct, headers=get_headers())

    df_ct = pd.DataFrame(response_2.json()['data'])
    data_1 = df_ct[['itemVnName', 'itemCode','displayLevel']].copy()

    data = pd.merge(data_1, pivot_df, left_on='itemCode', right_on='itemCode', how='left')
    data.drop('itemCode', axis=1, inplace=True)
    data.rename(columns={'itemVnName': 'Name'}, inplace=True)

    # Tách cột "Name" và các cột khác
    name_column = data['Name']
    other_columns = data.drop(columns=['Name'])

    # Đảo ngược thứ tự các cột khác
    other_columns = other_columns[other_columns.columns[::-1]]

    # Kết hợp lại với cột "Name"
    data = pd.concat([name_column, other_columns], axis=1)

    if timely in ['YEAR', 'NAM']:
        data.columns = [
            f"Năm {col.split('-')[0]}" if col not in ["Name", "displayLevel"] else col
            for col in data.columns
        ]
    elif timely in ['QUARTER', 'QUY']:
        data.columns = [
            f"Q1 {col[:4]}" if col.endswith('03-31') else
            f"Q2 {col[:4]}" if col.endswith('06-30') else
            f"Q3 {col[:4]}" if col.endswith('09-30') else
            f"Q4 {col[:4]}" if col.endswith('12-31') else col
            for col in data.columns
        ]

    # Tạo một danh sách chứa các ký tự để thêm vào
    prefixes_0 = ['A.', 'B.', 'C.', 'D.']  # cho displayLevel 0.0
    prefixes_1 = ['I.', 'II.', 'III.', 'IV.', 'V.', 'VI.', 'VII.', 'VIII.', 'IX.', 'X.', 'XI.', 'XII.', 'XIII.', 'XIV.', 'XV.', 'XVI.', 'XVII.', 'XVIII.', 'XIX.', 'XX.', 'XXI.', 'XXII.', 'XXIII.', 'XXIV.']  # cho displayLevel 1.0
    prefixes_2 = ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.', '11.', '12.', '13.', '14.', '15.', '16.', '17.', '18.', '19.', '20.', '21.', '22.', '23.', '24.']  # cho displayLevel 2.0
    prefixes_3 = ['a.', 'b.', 'c.', 'd.', 'e.', 'f.', 'g.', 'h.', 'i.', 'j.', 'k.', 'l.', 'm.', 'n.', 'o.', 'p.', 'q.', 'r.', 's.', 't.', 'u.', 'v.', 'w.', 'x.', 'y.', 'z.']  # cho displayLevel 3.0

    # Biến đếm cho các hàng
    count_0 = 0
    count_1 = 0
    count_2 = 0
    count_3 = 0

    # Vòng lặp để thêm ký tự vào đầu mỗi hàng dựa trên displayLevel
    for idx in data.index:
        display_level = data.at[idx, 'displayLevel']
        
        if display_level == 0.0:
            prefix = prefixes_0[count_0 % len(prefixes_0)]
            count_0 += 1
            # Reset bộ đếm cho cấp con khi gặp cấp cao hơn
            count_1, count_2, count_3 = 0, 0, 0
        elif display_level == 1.0:
            prefix = prefixes_1[count_1 % len(prefixes_1)]
            count_1 += 1
            count_2, count_3 = 0, 0
        elif display_level == 2.0:
            prefix = prefixes_2[count_2 % len(prefixes_2)]
            count_2 += 1
            count_3 = 0
        elif display_level == 3.0:
            prefix = prefixes_3[count_3 % len(prefixes_3)]
            count_3 += 1
        else:
            prefix = ''  # Không có tiền tố cho các cấp độ khác
        
        # Đảm bảo không có NaN trong cột 'Name'
        if pd.notna(data.at[idx, 'Name']):
            data.at[idx, 'Name'] = f"{prefix} {data.at[idx, 'Name']}"
        else:
            data.at[idx, 'Name'] = prefix  # Nếu giá trị rỗng thì chỉ thêm tiền tố

        # Danh sách các bank symbols
    bank_symbols = [
        "ABB", "ACB", "BAB", "BID", "BVB", "CTG", "EIB", "HDB", "KLB", "LPB", 
        "MBB", "MSB", "NAB", "NVB", "OCB", "PGB", "SGB", "SHB", "SSB", "STB", 
        "TCB", "TPB", "VAB", "VBB", "VCB", "VIB", "VPB"
    ]

    # Kiểm tra điều kiện symbol là bank symbol và types là bs
    if symbol in bank_symbols and types == 'BS':
        new_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 
                     21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 
                     39, 40, 41, 42, 43, 44, 45, 46, 47, 0, 50, 51, 52, 53, 54, 55, 56, 57, 
                     58, 59, 60, 61, 62, 49, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 
                     76, 77, 78, 63, 48, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 
                     92, 93, 94, 95, 96, 97, 98, 99]
        
        # Reset index để đảm bảo index liên tục từ 0
        data = data.reset_index(drop=True)
        
        # Lọc new_order để chỉ chứa các index tồn tại
        new_order = [i for i in new_order if i in data.index]
        
        # Áp dụng sắp xếp lại theo new_order
        data = data.reindex(new_order).reset_index(drop=True)

    elif symbol in bank_symbols and types == 'IC':
        new_order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 9, 12, 13, 14, 15, 16, 17, 19, 20, 18, 21, 22, 23, 24]
        
        # Reset index để đảm bảo index liên tục từ 0
        data = data.reset_index(drop=True)
        
        # Lọc new_order để chỉ chứa các index tồn tại
        new_order = [i for i in new_order if i in data.index]
        
        # Áp dụng sắp xếp lại theo new_order
        data = data.reindex(new_order).reset_index(drop=True)

    elif symbol in bank_symbols and types == 'CF':
        new_order = [
                0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 
                12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 
                32, 33, 34, 35, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 
                63, 64, 65, 66, 67, 68, 69, 70
        ]   
        # Reset index để đảm bảo index liên tục từ 0
        data = data.reset_index(drop=True)
        
        # Lọc new_order để chỉ chứa các index tồn tại
        new_order = [i for i in new_order if i in data.index]
        
        # Áp dụng sắp xếp lại theo new_order
        data = data.reindex(new_order).reset_index(drop=True)
    
    bs_dict_bank ={
        #tài sản
        "a. Góp vốn liên doanh": " - Góp vốn liên doanh",
        "b. Đầu tư vào công ty liên kết": " - Đầu tư vào công ty liên kết",
        "a. Nguyên giá TSCĐHH": " - Nguyên giá TSCĐHH",
        "b. Hao mòn TSCĐHH": " - Hao mòn TSCĐHH",
        "a. Nguyên giá TSCĐTTC": " - Nguyên giá TSCĐTTC",
        "b. Hao mòn TSCĐTTC": " - Hao mòn TSCĐTTC",
        "a. Nguyên giá TSCĐVH": " - Nguyên giá TSCĐVH",
        "b. Hao mòn TSCĐVH": " - Hao mòn TSCĐVH",
        "a. Trong đó: Lợi thế thương mại": " - Trong đó: Lợi thế thương mại",
        "A. TỔNG CỘNG TÀI SẢN": "A. Tổng cộng tài sản (I + ... + XII)",

        #nợ phải trả
        "II. Các khoản nợ Chính phủ và NHNN": "I. Các khoản nợ Chính phủ và NHNN",
        "III. Tiền gửi và vay các TCTD khác": "II. Tiền gửi và vay các TCTD khác",
        "IV. Tiền gửi của khách hàng": "III. Tiền gửi của khách hàng",
        "V. Các công cụ tài chính phái sinh và các khoản nợ tài chính khác": "IV. Các công cụ tài chính phái sinh và các khoản nợ tài chính khác",
        "VI. Vốn tài trợ, uỷ thác đầu tư, cho vay TCTD chịu rủi ro": "V. Vốn tài trợ, uỷ thác đầu tư, cho vay TCTD chịu rủi ro",
        "VII. Phát hành giấy tờ có giá": "VI. Phát hành giấy tờ có giá",
        "VIII. Các khoản nợ khác": "VII. Các khoản nợ khác",
        "I. Nợ phải trả": "C. Tổng nợ phải trả",

        #vốn chủ sở hữu
        "X. Vốn và các quỹ": "VIII. Vốn và các quỹ",
        "XI. Các Quỹ": "IX. Các Quỹ",
        "XII. Chênh lệch tỷ giá hối đoái": "X. Chênh lệch tỷ giá hối đoái   ",
        "XIII. Chênh lệch đánh giá lại tài sản": "XI. Chênh lệch đánh giá lại tài sản",
        "XIV. Lợi nhuận sau thuế chưa phân phối": "XII. Lợi nhuận sau thuế chưa phân phối",
        "XV. Lợi ích cổ đông không kiểm soát": "XIII. Lợi ích cổ đông không kiểm soát",
        "XVI. Lợi ích của cổ đông không kiểm soát (trước 2015)": "XIV. Lợi ích của cổ đông không kiểm soát (trước 2015)",
        "IX. Vốn chủ sở hữu": "D. Tổng vốn chủ sở hữu",
        "B. TỔNG CỘNG NGUỒN VỐN":"B. Tổng cộng nguồn vốn (C + D)",

        "C. Nghĩa vụ nợ tiềm ẩn": "E. Nghĩa vụ nợ tiềm ẩn",
        "D. Cam kết tín dụng": "F. Cam kết tín dụng",
    }

    ic_dict_bank = {
        "1. Thu nhập từ hoạt động dịch vụ":"3. Thu nhập từ hoạt động dịch vụ",
        "2. Chi phí hoạt động dịch vụ":"4. Chi phí hoạt động dịch vụ",
        "VIII. Tổng thu nhập hoạt động":"Tổng thu nhập hoạt động",
        "IX. Chi phí quản lý doanh nghiệp":"VIII. Chi phí quản lý doanh nghiệp",
        "X. Lợi nhuận thuần từ hoạt động kinh doanh trước chi phí dự phòng rủi ro tín dụng":"IX. Lợi nhuận thuần từ hoạt động kinh doanh trước chi phí dự phòng rủi ro tín dụng",
        "XI. Chi phí dự phòng rủi ro tín dụng":"X. Chi phí dự phòng rủi ro tín dụng",
        "XII. Lợi nhuận kế toán trước thuế":"XI. Lợi nhuận kế toán trước thuế",
        "XIII. Chi phí thuế TNDN":"XII. Chi phí thuế TNDN",
        "XIV. Lợi nhuận sau thuế thu nhập doanh nghiệp":"XIII. Lợi nhuận sau thuế thu nhập doanh nghiệp",
         "XV. Lợi ích của cổ đông thiểu số":"XIV. Lợi ích của cổ đông thiểu số",
        "XVI. Lợi nhuận sau thuế của Công ty mẹ":"XV. Lợi nhuận sau thuế của Công ty mẹ",
        "XVII. Lãi cơ bản trên cổ phiếu":"XVI. Lãi cơ bản trên cổ phiếu"
    }

    cf_dict_bank = {
        #gián tiếp
        "A. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG KINH DOANH - GIÁN TIẾP":"I. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG KINH DOANH - GIÁN TIẾP",
        "I. Lợi nhuận kế toán trước thuế":"1. Lợi nhuận kế toán trước thuế",
        "B. Điều chỉnh cho các khoản":"2. Điều chỉnh cho các khoản",
        "I. Chi phí khấu hao tài sản cố định":" - Chi phí khấu hao tài sản cố định",
        "II. Dự phòng rủi ro tín dụng, Giảm giá, đầu tư trích thêm,/(hoàn nhập) trong năm":" - Dự phòng rủi ro tín dụng, Giảm giá, đầu tư trích thêm,/(hoàn nhập) trong năm",
        "III. Lãi và phí phải thu trong kì (thực tế chưa thu) (*)":" - Lãi và phí phải thu trong kì (thực tế chưa thu) (*)",
        "IV. Lãi và phí phải trả trong kì (Thực tế chưa trả)":" - Lãi và phí phải trả trong kì (Thực tế chưa trả)",
        "V. Lãi lỗ do thanh lý TSCĐ":" - Lãi lỗ do thanh lý TSCĐ",
        "VI. Lãi lỗ do việc bán, thanh lý bất động sản":" - Lãi lỗ do việc bán, thanh lý bất động sản",
        "VII. Lãi lỗ do đầu tư vào đơn vị khác, cổ tức nhận được từ hoạt động đầu tư":" - Lãi lỗ do đầu tư vào đơn vị khác, cổ tức nhận được từ hoạt động đầu tư",
        "VIII. Chênh lệch tỷ giá hối đoái chưa thực hiện":" - Chênh lệch tỷ giá hối đoái chưa thực hiện",
        "IX. Các khoản điều chỉnh khác":" - Các khoản điều chỉnh khác",
        #trực tiếp
        "B. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG KINH DOANH - TRỰC TIẾP":"II. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG KINH DOANH - TRỰC TIẾP",
        "I. Thu nhập lãi và các khoản thu nhập tương tự":"1. Thu nhập lãi và các khoản thu nhập tương tự",
        "II. Chi phí lãi và các chi phí tương tự đã trả":"2. Chi phí lãi và các chi phí tương tự đã trả",
        "III. Thu nhập từ hoạt động dịch vụ nhận được":"3. Thu nhập từ hoạt động dịch vụ nhận được",
        "IV. Chênh lệch số tiền thực thu/thực chi từ hoạt động kinh doanh (vàng bạc, ngoại tệ, v.v…)":"4. Chênh lệch số tiền thực thu/thực chi từ hoạt động kinh doanh (vàng bạc, ngoại tệ, v.v…)",
        "V. Thu nhập từ hoạt động kinh doanh ngoại hối":"5. Thu nhập từ hoạt động kinh doanh ngoại hối",
        "VI. Thu nhập từ hoạt động kinh doanh chứng khoán":"6. Thu nhập từ hoạt động kinh doanh chứng khoán",
        "VII. Thu nhập khác":"7. Thu nhập khác",
        "VIII. Tiền thu các khoản nợ đã được xử lý xoá,bù đắp bằng nguồn rủi ro":"8. Tiền thu các khoản nợ đã được xử lý xoá,bù đắp bằng nguồn rủi ro",
        "IX. Tiền chi trả cho nhân viên và hoạt động quản lý, công vụ (*)":"9. Tiền chi trả cho nhân viên và hoạt động quản lý, công vụ (*)",
        "X. Tiền thuế thu nhập thực nộp trong kỳ (*)":"10. Tiền thuế thu nhập thực nộp trong kỳ (*)",
        "C. Lưu chuyển tiền thuần từ hoạt động kinh doanh trước những thay đổi về TS & vốn lưu động":"3. Lưu chuyển tiền thuần từ hoạt động kinh doanh trước những thay đổi về TS & vốn lưu động",
        #tài sản và công nợ hoạt động
        "D. Những thay đổi về tài sản và công nợ hoạt động":"Những thay đổi về tài sản và công nợ hoạt động",
        #tài sản hoạt động
        "I. Những thay đổi về tài sản hoạt động":"A. Những thay đổi về tài sản hoạt động",
        "1. Tăng/ (Giảm) tiền gửi dự trữ bắt buộc tại NHNN":" - Tăng/ (Giảm) tiền gửi dự trữ bắt buộc tại NHNN",
        "2. Tăng/ (Giảm) các khoản tiền gửi, tiền vay các tổ chức tín dụng khác":" - Tăng/ (Giảm) các khoản tiền gửi, tiền vay các tổ chức tín dụng khác",
        "3. Tăng/ (Giảm) chứng khoán kinh doanh":" - Tăng/ (Giảm) chứng khoán kinh doanh",
        "4. Tăng/ (Giảm) các công cụ tài chính phái sinh và các tài sản tài chính khác":" - Tăng/ (Giảm) các công cụ tài chính phái sinh và các tài sản tài chính khác",
        "5. Tăng/ (Giảm) các khoản cho vay, ứng trước khách hàng":" - Tăng/ (Giảm) các khoản cho vay, ứng trước khách hàng",
        "6. Tăng)/Giảm lãi, phí phải thu":" - Tăng)/Giảm lãi, phí phải thu",
        "7. Giảm/ (Tăng) nguồn dự phòng để bù đắp tổn thất các khoản":" - Giảm/ (Tăng) nguồn dự phòng để bù đắp tổn thất các khoản",
        "8. Tăng/ (Giảm) khác về tài sản hoạt động":" - Tăng/ (Giảm) khác về tài sản hoạt động",
        #công nợ hoạt động
        "II. Những thay đổi về công nợ hoạt động":"B. Những thay đổi về công nợ hoạt động",
        "1. Tăng/ (Giảm) các khoản tiền vay NHNN":" - Tăng/ (Giảm) các khoản tiền vay NHNN",
        "2. Tăng/ (Giảm) các khoản tiền gửi, tiền vay các tổ chức tín dụng":" - Tăng/ (Giảm) các khoản tiền gửi, tiền vay các tổ chức tín dụng",
        "3. Tăng/ (Giảm) tiền gửi của khách hàng (bao gồm cả Kho bạc Nhà nước)":" - Tăng/ (Giảm) tiền gửi của khách hàng (bao gồm cả Kho bạc Nhà nước)",
        "4. Tăng/ (Giảm) các công cụ tài chính phái sinh và các khoản nợ tài chính khác":" - Tăng/ (Giảm) các công cụ tài chính phái sinh và các khoản nợ tài chính khác",
        "5. Tăng/ (Giảm) vốn tài trợ, uỷ thác đầu tư, cho vay mà TCTD chịu rủi ro":" - Tăng/ (Giảm) vốn tài trợ, uỷ thác đầu tư, cho vay mà TCTD chịu rủi ro",
        "6. Tăng/ (Giảm) phát hành GTCG (ngoại trừ GTCG phát hành được tính vào hoạt động tài chính)":" - Tăng/ (Giảm) phát hành GTCG (ngoại trừ GTCG phát hành được tính vào hoạt động tài chính)",
        "7. Tăng/ (Giảm) lãi, phí phải trả":" - Tăng/ (Giảm) lãi, phí phải trả",
        "8. Tăng/ (Giảm) khác về công nợ hoạt động":" - Tăng/ (Giảm) khác về công nợ hoạt động",
        #trước thuế thu nhập
        "A. Lưu chuyển tiền tệ thuần từ hoạt động kinh doanh trước thuế thu nhập":"4. Lưu chuyển tiền tệ thuần từ hoạt động kinh doanh trước thuế thu nhập",
        "I. Thuế TNDN đã nộp (*)":" - Thuế TNDN đã nộp (*)",
        "II. Chi từ các quỹ của TCTD (*)":" - Chi từ các quỹ của TCTD (*)",
        "III. Thu được từ nợ khó đòi":" - Thu được từ nợ khó đòi",

        "C. Lưu chuyển tiền thuần từ hoạt động kinh doanh":"Lưu chuyển tiền thuần từ hoạt động kinh doanh",
        #ĐẦU TƯ
        "D. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG ĐẦU TƯ":"III. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG ĐẦU TƯ",
        "I. Mua sắm TSCĐ":"1. Mua sắm TSCĐ",
        "II. Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác":"2. Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác",
        "III. Tiền chi từ thanh lý, nhượng bán TSCĐ":"3. Tiền chi từ thanh lý, nhượng bán TSCĐ",
        "IV. Mua sắm bất động sản đầu tư":"4. Mua sắm bất động sản đầu tư",
        "V. Tiền thu từ bán, thanh lý bất động sản đầu tư":"5. Tiền thu từ bán, thanh lý bất động sản đầu tư",
        "VI. Tiền chi ra do bán, thanh lý bất động sản đầu tư":"6. Tiền chi ra do bán, thanh lý bất động sản đầu tư",
        "VII. Tiền chi đầu tư góp vốn vào đơn vị khác":"7. Tiền chi đầu tư góp vốn vào đơn vị khác",
        "VIII. Tiền thu hồi đầu tư góp vốn vào đơn vị khác":"8. Tiền thu hồi đầu tư góp vốn vào đơn vị khác",
        "IX. Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia":"9. Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia",
        "A. Lưu chuyển tiền thuần từ hoạt động đầu tư":"5. Lưu chuyển tiền thuần từ hoạt động đầu tư",
        #tài chính
        "B. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG TÀI CHÍNH":"IV. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG TÀI CHÍNH",
        "I. Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu":"1. Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu",
        "II. Tiền thu từ PH GTCG dài hạn có đủ đk tính vào vốn tự có & các khoản vốn vay dài hạn khác":"2. Tiền thu từ PH GTCG dài hạn có đủ đk tính vào vốn tự có & các khoản vốn vay dài hạn khác",
        "III. Tiền chi từ PH GTCG dài hạn có đủ đk tính vào vốn tự có & các khoản vốn vay dài hạn khác":"3. Tiền chi từ PH GTCG dài hạn có đủ đk tính vào vốn tự có & các khoản vốn vay dài hạn khác",
        "IV. Cổ tức, lợi nhuận đã trả cho chủ sở hữu":"4. Cổ tức, lợi nhuận đã trả cho chủ sở hữu",
        "V. Tiền chi trả vốn góp cho các chủ sở hữu, mua lại cổ phiếu của doanh nghiệp đã phát hành":"5. Tiền chi trả vốn góp cho các chủ sở hữu, mua lại cổ phiếu của doanh nghiệp đã phát hành",
        "VI. Tiền thu được do bán/mua cổ phiếu ngân quỹ":"6. Tiền thu được do bán/mua cổ phiếu ngân quỹ",
        "C. Lưu chuyển tiền thuần từ hoạt động tài chính":"7. Lưu chuyển tiền thuần từ hoạt động tài chính",
        #
        "D. Lưu chuyển tiền thuần trong kỳ":"Lưu chuyển tiền thuần trong kỳ",
        "A. Tiền và tương đương tiền đầu kỳ":"Tiền và tương đương tiền đầu kỳ",
        "B. Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ":"Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ",
        "C. Tiền và tương đương tiền cuối kỳ":"Tiền và tương đương tiền cuối kỳ"
    }

    bs_dict_normal = {
        #tài sản ngắn hạn
        "I. Tài sản ngắn hạn": "A. Tổng tài sản ngắn hạn (I + II + II + IV + V)",
        "1. Tiền và các khoản tương đương tiền": "I. Tiền và các khoản tương đương tiền",
        "a. Tiền": "1. Tiền",
        "b. Các khoản tương đương tiền": "2. Các khoản tương đương tiền",
        "2. Các khoản đầu tư tài chính ngắn hạn": "II. Đầu tư tài chính ngắn hạn",
        "a. Đầu tư ngắn hạn": "1. Chứng khoán kinh doanh",
        "b. Dự phòng giảm giá đầu tư ngắn hạn": "2. Dự phòng giảm giá chứng khoán kinh doanh (*)",
        "c. Đầu tư giữ đến ngày đáo hạn": "3. Đầu tư nắm giữ đến ngày đáo hạn",
        "3. Các khoản phải thu ngắn hạn": "III. Các khoản phải thu ngắn hạn",
        "a. Phải thu khách hàng": "1. Phải thu ngắn hạn của khách hàng",
        "b. Trả trước cho người bán": "2. Trả trước cho người bán ngắn hạn",
        "c. Phải thu nội bộ ngắn hạn": "3. Phải thu nội bộ ngắn hạn",
        "d. Phải thu theo tiến độ kế hoạch hợp đồng xây dựng": "4. Phải thu theo tiến độ kế hoạch hợp đồng xây dựng",
        "e. Phải thu về cho vay ngắn hạn": "5. Phải thu về cho vay ngắn hạn",
        "f. Các khoản phải thu khác": "6. Phải thu ngắn hạn khác",
        "g. Dự phòng phải thu ngắn hạn khó đòi": "7. Dự phòng các khoản phải thu ngắn hạn khó đòi (*)",
        "h. Tài sản thiếu chờ xử lý": "8. Tài sản thiếu chờ xử lý",
        "4. Hàng tồn kho": "IV. Hàng tồn kho",
        "a. Hàng tồn kho": "1. Hàng tồn kho",
        "b. Dự phòng giảm giá hàng tồn kho": "2. Dự phòng giảm giá hàng tồn kho (*)",
        "5. Tài sản ngắn hạn khác": "V. Tài sản ngắn hạn khác",
        "a. Chi phí trả trước ngắn hạn": "1. Chi phi trả trước ngắn hạn",
        "b. Thuế GTGT được khấu trừ": "2. Thuế giá trị gia tăng được khấu trừ",
        "c. Thuế và các khoản khác phải thu Nhà nước": "3. Thuế và các khoản khác phải thu Nhà nước",
        "d. Giao dịch mua bán lại trái phiếu chính phủ": "4. Giao dịch mua bán lại trái phiếu Chính phủ",
        "e. Tài sản ngắn hạn khác": "5. Tài sản ngắn hạn khác",
        #tài sản dài hạn
        "II. Tài sản dài hạn": "B. Tổng tài sản dài hạn (I + II + II + IV + V + VI + VII)",
        "1. Các khoản phải thu dài hạn": "I. Các khoản phải thu dài hạn",
        "a. Phải thu dài hạn của khách hàng": "1. Phải thu dài hạn của khách hàng",
        "b. Trả trước dài hạn người bán": "2. Trả trước cho người bán dài hạn",
        "c. Vốn kinh doanh ở đơn vị trực thuộc": "3. Vốn kinh doanh ở đơn vị trực thuộc",
        "d. Phải thu dài hạn nội bộ": "4. Phải thu nội bộ dài hạn",
        "e. Phải thu về cho vay dài hạn": "5. Phải thu về cho vay dài hạn",
        "f. Phải thu dài hạn khác": "6. Phải thu dài hạn khác",
        "g. Dự phòng phải thu dài hạn khó đòi": "7. Dự phòng phải thu dài hạn khó đòi (*)",
        "2. Tài sản cố định": "II. Tài sản cố định",
        "a. Tài sản cố định hữu hình": "1. Tài sản cố định hữu hình",
        "b. Tài sản cố định thuê tài chính": "2. Tài sản cố định thuê tài chính",
        "c. Tài sản cố định vô hình": "3. Tài sản cố định vô hình",
        "d. Chi phí xây dựng cơ bản dở dang (trước 2015)": "4. Chi phí xây dựng cơ bản dở dang (trước 2015)",
        "3. Bất động sản đầu tư": "III. Bất động sản đầu tư",
        "a. Nguyên giá bất động sản đầu tư": "1. Nguyên giá",
        "b. Hao mòn bất động sản đầu tư": "2. Giá trị hao mòn lũy kế (*)",
        "4. Tài sản dở dang dài hạn": "IV. Tài sản dở dang dài hạn",
        "a. Chi phí sản xuất, kinh doanh dở dang dài hạn": "1. Chi phí sản xuất, kinh doanh dở dang dài hạn",
        "b. Chi phí xây dựng cơ bản dở dang ": "2. Chi phí xây dựng cơ bản dở dang",
        "5. Các khoản đầu tư tài chính dài hạn": "V. Đầu tư tài chính dài hạn",
        "a. Đầu tư vào công ty con": "1. Đầu tư vào công ty con",
        "b. Đầu tư vào công ty liên kết, liên doanh": "2. Đầu tư vào công ty liên doanh, liên kết",
        "c. Đầu tư dài hạn khác": "3. Đầu tư góp vốn vào đơn vị khác",
        "d. Dự phòng giảm giá đầu tư tài chính dài hạn": "4. Dự phòng đầu tư tài chính dài hạn (*)",
        "e. Đầu tư dài hạn giữ đến ngày đáo hạn": "5. Đầu tư nắm giữ đến ngày đáo hạn",
        "6. Tài sản dài hạn khác": "VI. Tài sản dài hạn khác",
        "a. Chi phí trả trước dài hạn": "1. Chi phí trả trước dài hạn",
        "b. Tài sản thuế thu nhập hoãn lại": "2. Tài sản thuế thu nhập hoãn lại",
        "c. Thiết bị, vật tư, phụ tùng thay thế dài hạn": "3. Thiết bị, vật tư, phụ tùng thay thế dài hạn",
        "d. Tài sản dài hạn khác": "4. Tài sản dài hạn khác",
        "e. Lợi thế thương mại": "5. Lợi thế thương mại",
        "7. Lợi thế thương mại (trước 2015)": "VII. Lợi thế thương mại (trước 2015)",
        #Tổng tài sản
        "A. TỔNG CỘNG TÀI SẢN": "Tổng cộng tài sản (A + B)",
        #Tổng phải trả
        "I. Nợ phải trả": "C. Tổng nợ phải trả (I + II)",
        #Nợ ngắn hạn
        "1. Nợ ngắn hạn": "I. Nợ ngắn hạn",
        "a. Vay và nợ ngắn hạn": "1. Vay và nợ ngắn hạn",
        "b. Phải trả người bán": "2. Phải trả người bán",
        "c. Người mua trả tiền trước": "3. Người mua trả tiền trước",
        "d. Thuế và các khoản phải nộp Nhà nước": "4. Thuế và các khoản phải nộp Nhà nước",
        "e. Phải trả người lao động": "5. Phải trả người lao động",
        "f. Chi phí phải trả": "6. Chi phí phải trả",
        "g. Phải trả nội bộ": "7. Phải trả nội bộ",
        "h. Phải trả theo tiến độ kế hoạch hợp đồng xây dựng": "8. Phải trả theo tiến độ kế hoạch hợp đồng xây dựng",
        "i. Các khoản phải trả, phải nộp ngắn hạn khác": "9. Các khoản phải trả, phải nộp ngắn hạn khác",
        "j. Quỹ khen thưởng, phúc lợi": "10. Quỹ khen thưởng, phúc lợi",
        "k. Doanh thu chưa thực hiện ngắn hạn": "11. Doanh thu chưa thực hiện ngắn hạn",
        "l. Dự phòng phải trả ngắn hạn": "12. Dự phòng phải trả ngắn hạn",
        "m. Quỹ bình ổn giá": "13. Quỹ bình ổn giá",
        "n. Giao dịch mua bán lại trái phiếu chính phủ": "14. Giao dịch mua bán lại trái phiếu chính phủ",
        #Nợ dài hạn
        "2. Nợ dài hạn": "II. Nợ dài hạn",
        "a. Phải trả dài hạn người bán": "1. Phải trả dài hạn người bán",
        "b. Người mua trả trước dài hạn": "2. Người mua trả trước dài hạn",
        "c. Chi phí phải trả dài hạn": "3. Chi phí phải trả dài hạn",
        "d. Phải trả nội bộ về vốn kinh doanh": "4. Phải trả nội bộ về vốn kinh doanh",
        "e. Phải trả dài hạn nội bộ": "5. Phải trả dài hạn nội bộ",
        "f. Phải trả dài hạn khác": "6. Phải trả dài hạn khác",
        "g. Vay và nợ dài hạn": "7. Vay và nợ dài hạn",
        "h. Trái phiếu chuyển đổi": "8. Trái phiếu chuyển đổi",
        "i. Cổ phiếu ưu đãi": "9. Cổ phiếu ưu đãi",
        "j. Thuế thu nhập hoãn lại phải trả": "10. Thuế thu nhập hoãn lại phải trả",
        "k. Dự phòng trợ cấp mất việc làm": "11. Dự phòng trợ cấp mất việc làm",
        "l. Doanh thu chưa thực hiện dài hạn": "12. Doanh thu chưa thực hiện dài hạn",
        "m. Quỹ phát triển khoa học và công nghệ": "13. Quỹ phát triển khoa học và công nghệ",
        "n. Dự phòng phải trả dài hạn": "14. Dự phòng phải trả dài hạn",
        #Tổng vốn chủ sở hữu
        "II. Vốn chủ sở hữu": "D. Tổng vốn chủ sở hữu (I + II + III)",
        "1. Vốn và các quỹ": "I. Vốn và các quỹ",
        "a. Vốn góp": "1. Vốn góp",
        "b. Thặng dư vốn cổ phần": "2. Thặng dư vốn cổ phần",
        "c. Quyền chọn chuyển đổi trái phiếu": "3. Quyền chọn chuyển đổi trái phiếu",
        "d. Vốn khác của chủ sở hữu": "4. Vốn khác của chủ sở hữu",
        "e. Cổ phiếu quỹ": "5. Cổ phiếu quỹ",
        "f. Chênh lệch đánh giá lại tài sản": "6. Chênh lệch đánh giá lại tài sản",
        "g. Chênh lệch tỷ giá hối đoái": "7. Chênh lệch tỷ giá hối đoái",
        "h. Quỹ đầu tư phát triển": "8. Quỹ đầu tư phát triển",
        "i. Quỹ dự phòng tài chính": "9. Quỹ dự phòng tài chính",
        "j. Quỹ khác thuộc vốn chủ sở hữu": "10. Quỹ khác thuộc vốn chủ sở hữu",
        "k. Lợi nhuận sau thuế chưa phân phối": "11. Lợi nhuận sau thuế chưa phân phối",
        "l. Lợi ích cổ đông không kiểm soát": "12. Lợi ích cổ đông không kiểm soát",
        "m. Quỹ hỗ trợ sắp xếp doanh nghiệp": "13. Quỹ hỗ trợ sắp xếp doanh nghiệp",
        "n. Nguồn vốn đầu tư XDCB": "14. Nguồn vốn đầu tư XDCB",
        "2. Nguồn kinh phí và quỹ khác": "II. Nguồn kinh phí và quỹ khác",
        "a. Quỹ khen thưởng, phúc lợi (trước 2010)": "1. Quỹ khen thưởng, phúc lợi (trước 2010)",
        "b. Vốn ngân sách nhà nước": "2. Vốn ngân sách nhà nước",
        "c. Nguồn kinh phí đã hình thành TSCĐ": "3. Nguồn kinh phí đã hình thành TSCĐ",
        "III. Lợi ích của cổ đông không kiểm soát (trước 2015)": "III. Lợi ích của cổ đông không kiểm soát (trước 2015)",
        #tổng nguồn vốn
        "B. TỔNG CỘNG NGUỒN VỐN": "Tổng cộng nguồn vốn (C + D)"
    }

    ic_dict_normal = {
        
        "I. Tổng doanh thu hoạt động kinh doanh": "1. Doanh thu bán hàng và cung cấp dịch vụ",
        "II. Các khoản giảm trừ doanh thu": "2. Các khoản giảm trừ doanh thu",
        "III. Doanh thu thuần": "3. Doanh thu thuần về bán hàng và cung cấp dịch vụ (1 - 2)",
        "IV. Giá vốn hàng bán": "4. Giá vốn hàng bán",
        "V. Lợi nhuận gộp": "5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ (3 - 4)",
        "VI. Doanh thu hoạt động tài chính": "6. Doanh thu hoạt động tài chính",
        "VII. Chi phí tài chính": "7. Chi phí tài chính",
        "1. Trong đó: Chi phí lãi vay": " - Trong đó: Chi phí lãi vay ",
        "VIII. Lợi nhuận hoặc lỗ trong công ty liên kết": "8. Lợi nhuận hoặc lỗ trong công ty liên kết",
        "IX. Chi phí bán hàng": "9. Chi phí bán hàng",
        "X. Chi phí quản lý doanh nghiệp": "10. Chi phí quản lý doanh nghiệp",
        "XI. Lợi nhuận thuần từ hoạt động kinh doanh": "11. Lợi nhuận thuần từ hoạt động kinh doanh [5 + (6 - 7) + 8 - (9 + 10)]",
        "XII. Thu nhập khác": "12. Thu nhập khác",
        "XIII. Chi phí khác": "13. Chi phí khác",
        "XIV. Lợi nhuận khác": "14. Lợi nhuận khác (12 - 13)",
        "XV. Lợi nhuận hoặc lỗ trong công ty liên kết (trước 2015)": "15. Lợi nhuận hoặc lỗ trong công ty liên kết (trước 2015)",
        "XVI. Lợi nhuận kế toán trước thuế": "16. Lợi nhuận kế toán trước thuế",
        "XVII. Chi phí thuế TNDN": "17. Chi phí thuế TNDN (hiện hành + hoãn lại)",
        "1. Chi phí thuế TNDN hiện hành": " - Chi phí thuế TNDN hiện hành",
        "2. Chi phí thuế TNDN hoãn lại": " - Chi phí thuế TNDN hoãn lại",
        "XVIII. Lợi nhuận sau thuế thu nhập doanh nghiệp": "18. Lợi nhuận sau thuế thu nhập doanh nghiệp (16 - 17)",
        "XIX. Lợi ích của cổ đông thiểu số": "19. Lợi ích của cổ đông thiểu số",
        "XX. Lợi nhuận sau thuế của Công ty mẹ": "20. Lợi nhuận sau thuế của Công ty mẹ",
        "XXI. Lãi cơ bản trên cổ phiếu": "21. Lãi cơ bản trên cổ phiếu",
        "XXII. Lãi suy giảm trên cổ phiếu": "22. Lãi suy giảm trên cổ phiếu",
    }

    cf_dict_normal = {
        "A. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG KINH DOANH - GIÁN TIẾP":"I. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG KINH DOANH - GIÁN TIẾP",
        "I. Lợi nhuận kế toán trước thuế":"1. Lợi nhuận kế toán trước thuế",
        "B. Điều chỉnh cho các khoản":"2. Điều chỉnh cho các khoản",
        "I. Chi phí khấu hao tài sản cố định":" - Chi phí khấu hao tài sản cố định",
        "II. Phân bổ lợi thế thương mại":" - Phân bổ lợi thế thương mại",
        "III. Dự phòng giảm giá các khoản đầu tư ngắn hạn, dài hạn":" - Dự phòng giảm giá các khoản đầu tư ngắn hạn, dài hạn",
        "IV. Lãi, lỗ chênh lệch tỷ giá hối đoái chưa thực hiện":" - Lãi, lỗ chênh lệch tỷ giá hối đoái chưa thực hiện",
        "V. Lãi/(lỗ) từ thanh lý tài sản cố định":" - Lãi/(lỗ) từ thanh lý tài sản cố định",
        "VI. Lãi, lỗ từ hoạt động đầu tư":" - Lãi, lỗ từ hoạt động đầu tư",
        "VII. Chi phí lãi vay":" - Chi phí lãi vay",
        "VIII. Thu lãi và cổ tức":" - Thu lãi và cổ tức",
        "IX. Các khoản điều chỉnh khác":" - Các khoản điều chỉnh khác",
        "C. Lợi nhuận từ hoạt động kinh doanh trước thay đổi vốn  lưu động":"3. Lợi nhuận từ hoạt động kinh doanh trước thay đổi vốn  lưu động",
        "I. Tăng, giảm các khoản phải thu":" - Tăng, giảm các khoản phải thu",
        "II. Tăng, giảm hàng tồn kho":" - Tăng, giảm hàng tồn kho",
        "III. Tăng, giảm các khoản phải trả (Không kể lãi vay phải trả, thuế TNDN phải nộp)":" - Tăng, giảm các khoản phải trả (Không kể lãi vay phải trả, thuế TNDN phải nộp)",
        "IV. Tăng, giảm chi phí trả trước":" - Tăng, giảm chi phí trả trước",
        "V. Tăng/ (Giảm) chứng khoán kinh doanh":" - Tăng/ (Giảm) chứng khoán kinh doanh",
        "VI. Tiền lãi vay đã trả":" - Tiền lãi vay đã trả",
        "VII. Thuế thu nhập doanh nghiệp đã nộp":" - Thuế thu nhập doanh nghiệp đã nộp",
        "VIII. Tiền thu khác từ hoạt động kinh doanh":" - Tiền thu khác từ hoạt động kinh doanh",
        "IX. Tiền chi khác cho hoạt động kinh doanh":" - Tiền chi khác cho hoạt động kinh doanh",

        "D. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG KINH DOANH - TRỰC TIẾP":"II. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG KINH DOANH - TRỰC TIẾP",
        "I. Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác":"1. Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác",
        "II. Tiền chi trả cho người cung cấp hàng hóa và dịch vụ":"2. Tiền chi trả cho người cung cấp hàng hóa và dịch vụ",
        "III. Tiền chi trả cho người lao động":"3. Tiền chi trả cho người lao động",
        "IV. Tiền chi trả lãi vay":"4. Tiền chi trả lãi vay",
        "V. Tiền chi nộp thuế thu nhập doanh nghiệp":"5. Tiền chi nộp thuế thu nhập doanh nghiệp",
        "VI. Tiền thu khác từ hoạt động kinh doanh":"6. Tiền thu khác từ hoạt động kinh doanh",
        "VII. Tiền chi khác cho hoạt động kinh doanh":"7. Tiền chi khác cho hoạt động kinh doanh",
        "A. Lưu chuyển tiền thuần từ hoạt động kinh doanh":"20. Lưu chuyển tiền thuần từ hoạt động kinh doanh",

        "B. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG ĐẦU TƯ":"III. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG ĐẦU TƯ",
        "I. Mua sắm TSCĐ":"1. Mua sắm TSCĐ",
        "II. Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác":"2. Tiền thu từ thanh lý, nhượng bán TSCĐ và các tài sản dài hạn khác",
        "III. Tiền chi cho vay, mua các công cụ nợ của đơn vị khác":"3. Tiền chi cho vay, mua các công cụ nợ của đơn vị khá",
        "IV. Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác":"4. Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác",
        "V. Tiền chi đầu tư góp vốn vào đơn vị khác":"5. Tiền chi đầu tư góp vốn vào đơn vị khác",
        "VI. Tiền thu hồi đầu tư góp vốn vào đơn vị khác":"6. Tiền thu hồi đầu tư góp vốn vào đơn vị khác",
        "VII. Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia":"7. Tiền thu lãi cho vay, cổ tức và lợi nhuận được chia",
        "C. Lưu chuyển tiền thuần từ hoạt động đầu tư":"30. Lưu chuyển tiền thuần từ hoạt động đầu tư",

        "D. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG TÀI CHÍNH":"IV. LƯU CHUYỂN TIỀN TỪ HOẠT ĐỘNG TÀI CHÍNH",
        "I. Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu":"1. Tiền thu từ phát hành cổ phiếu, nhận vốn góp của chủ sở hữu",
        "II. Tiền chi trả vốn góp cho các chủ sở hữu, mua lại cổ phiếu của doanh nghiệp đã phát hành":"2. Tiền chi trả vốn góp cho các chủ sở hữu, mua lại cổ phiếu của doanh nghiệp đã phát hành",
        "III. Tiền vay ngắn hạn, dài hạn nhận được":"3. Tiền vay ngắn hạn, dài hạn nhận được",
        "IV. Tiền chi trả nợ gốc vay":"4. Tiền chi trả nợ gốc vay",
        "V. Tiền chi trả nợ thuê tài chính":"5. Tiền chi trả nợ thuê tài chính",
        "VI. Cổ tức, lợi nhuận đã trả cho chủ sở hữu":"6. Cổ tức, lợi nhuận đã trả cho chủ sở hữu",
        "VII. Tiền lãi đã nhận":"7. Tiền lãi đã nhận",
        "A. Lưu chuyển tiền thuần từ hoạt động tài chính":"40. Lưu chuyển tiền thuần từ hoạt động tài chính",
        
        "B. Lưu chuyển tiền thuần trong kỳ":"50. Lưu chuyển tiền thuần trong kỳ (20 + 30 + 40)",
        "C. Tiền và tương đương tiền đầu kỳ":"60. Tiền và tương đương tiền đầu kỳ",
        "D. Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ":"61. Ảnh hưởng của thay đổi tỷ giá hối đoái quy đổi ngoại tệ",
        "A. Tiền và tương đương tiền cuối kỳ":"Tiền và tương đương tiền cuối kỳ (50 + 60 + 61)"
    }

    def get_dict(types, symbol):
    # Danh sách các ticker thuộc ngân hàng
        bank_symbols = ["ABB","ACB","BAB","BID","BVB","CTG","EIB","HDB","KLB","LPB","MBB","MSB","NAB","NVB","OCB","PGB","SGB","SHB","SSB","STB","TCB","TPB","VAB","VBB","VCB","VIB","VPB"]
        
        # Kiểm tra loại báo cáo và ticker
        if symbol in bank_symbols:
            if types == "BS":
                return bs_dict_bank  # Từ điển bảng cân đối kế toán cho ngân hàng
            elif types == "IC":
                return ic_dict_bank  # Từ điển kết quả kinh doanh cho ngân hàng
            elif types == "CF":
                return cf_dict_bank  # Từ điển lưu chuyển tiền tệ cho ngân hàng
        else:
            if types == "BS":
                return bs_dict_normal  # Từ điển bảng cân đối kế toán thông thường
            elif types == "IC":
                return ic_dict_normal  # Từ điển kết quả kinh doanh thông thường
            elif types == "CF":
                return cf_dict_normal  # Từ điển lưu chuyển tiền tệ thông thường
        
        # Nếu không khớp với loại báo cáo nào
        raise ValueError("Invalid types parameter")

    # Lấy từ điển tương ứng với loại báo cáo
    rename_dict = get_dict(types, symbol)

    # Áp dụng đổi tên
    for old_value, new_value in rename_dict.items():
        data.loc[data["Name"] == old_value, "Name"] = new_value

    data = data.fillna(0)   
    data.drop(columns=['displayLevel'], inplace=True)
    
    return data

def price_stock(symbol, fromdate, todate):
    symbol = symbol.upper()

    # Convert dates to the correct format
    fromdate = datetime.strptime(fromdate, '%Y-%m-%d').strftime('%Y-%m-%d')
    todate = datetime.strptime(todate, '%Y-%m-%d').strftime('%Y-%m-%d')

    all_data = pd.DataFrame()
    page = 1  # Bắt đầu từ trang đầu tiên

    while True:
        # API URL với tham số page
        url = f'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date&q=code:{symbol}~date:gte:{fromdate}~date:lte:{todate}&page={page}'

        # Gửi request đến API
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            # Lấy dữ liệu từ response
            data = response.json().get('data', [])
            if not data:  # Nếu không còn dữ liệu, thoát vòng lặp
                break
            
            # Chuyển đổi dữ liệu thành DataFrame
            df = pd.DataFrame(data)
            if not df.empty:
                # Lọc các cột cần thiết
                df = df[['date', 'open', 'high', 'low', 'close', 'nmVolume']]
                df.rename(columns={'nmVolume': 'Volume'}, inplace=True)
                # Kết hợp dữ liệu của các trang
                all_data = pd.concat([all_data, df], ignore_index=True)
            page += 1  # Tăng trang tiếp theo
        else:
            print(f"Error: {response.status_code} - {response.text}")
            break

    return all_data

def macroeconomics_report(url, report_type, from_year, to_year, from_month=None, to_month=None):
    """Lấy dữ liệu từ trang web và trả về DataFrame"""

    # Cấu hình Chrome cho chế độ không hiển thị
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Chạy ở chế độ không hiển thị
    chrome_options.add_argument('--no-sandbox')  # Bỏ qua sandbox
    chrome_options.add_argument('--disable-dev-shm-usage')  # Khắc phục lỗi shared memory
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('blink-settings=imagesEnabled=false')  # Tắt tải hình ảnh

    # Khởi động driver
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Mở trang web
        driver.get(url=url)

        # Chọn loại báo cáo
        select_type = Select(driver.find_element(By.NAME, 'type'))
        select_type.select_by_value(report_type)

        # Chọn năm
        select_from_year = Select(driver.find_element(By.NAME, 'fromYear'))
        select_from_year.select_by_value(str(from_year))

        select_to_year = Select(driver.find_element(By.NAME, 'toYear'))
        select_to_year.select_by_value(str(to_year))

        # Nếu là báo cáo theo tháng (report_type = 2), chọn tháng bắt đầu và kết thúc
        if report_type == '2':
            if from_month:
                select_from_month = Select(driver.find_element(By.NAME, 'from'))
                select_from_month.select_by_value(str(from_month))

            if to_month:
                select_to_month = Select(driver.find_element(By.NAME, 'to'))
                select_to_month.select_by_value(str(to_month))

        # Nhấn nút "Xem"
        driver.find_element(By.CLASS_NAME, 'btn.bg.m-l').click()
        time.sleep(5)  # Đợi trang tải hoàn tất

        # Lấy nội dung trang
        content = driver.page_source

        # Phân tích dữ liệu từ HTML
        soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table', id='tbl-macro-data')  # Giả sử dữ liệu là một bảng
        rows = table.find_all('tr')

        header = []
        data = []

        # Lấy tên bảng
        table_name = soup.find('tr', class_='i-bg5')
        if table_name:
            rows_table_name = table_name.find_all('th')
            header = [th.text.strip() for th in rows_table_name]

        # Duyệt qua các hàng và lấy text từ các cột <td>
        for row in rows:
            cols = row.find_all('td')
            if cols:
                col_texts = [col.text.strip() for col in cols]  # Lấy text và bỏ khoảng trắng thừa
                data.append(col_texts)

        # Tạo DataFrame từ dữ liệu
        df = pd.DataFrame(data, columns=header)
        return df

    finally:
        # Đóng trình duyệt
        driver.quit()

def cpi_report(report_type, from_year, to_year, from_month=None, to_month=None):
    # Sử dụng hàm để lấy dữ liệu
    df = macroeconomics_report(
        url='https://finance.vietstock.vn/du-lieu-vi-mo/52/cpi.htm',
        report_type=report_type,
        from_year=from_year,
        to_year=to_year,
        from_month=from_month,
        to_month=to_month)

    return df

def retail_report(report_type, from_year, to_year, from_month=None, to_month=None):
    # Sử dụng hàm để lấy dữ liệu
    final_df = macroeconomics_report(
        url='https://finance.vietstock.vn/du-lieu-vi-mo/47/ban-le.htm',
        report_type=report_type,
        from_year=from_year,
        to_year=to_year,
        from_month=from_month,
        to_month=to_month)

    return final_df

def sxcn_report(report_type, from_year, to_year, from_month=None, to_month=None):
    # Sử dụng hàm để lấy dữ liệu
    df = macroeconomics_report(
        url='https://finance.vietstock.vn/du-lieu-vi-mo/46/san-xuat-cong-nghiep.htm',
        report_type=report_type,
        from_year=from_year,
        to_year=to_year,
        from_month=from_month,
        to_month=to_month)

    return df

def xnk_report(report_type, from_year, to_year, from_month=None, to_month=None):
    # Sử dụng hàm để lấy dữ liệu
    df = macroeconomics_report(
        url='https://finance.vietstock.vn/du-lieu-vi-mo/48-49/xuat-nhap-khau.htm',
        report_type=report_type,
        from_year=from_year,
        to_year=to_year,
        from_month=from_month,
        to_month=to_month)

    return df

def fdi_report(report_type, from_year, to_year, from_month=None, to_month=None):
    # Sử dụng hàm để lấy dữ liệu
    df = macroeconomics_report(
        url='https://finance.vietstock.vn/du-lieu-vi-mo/50/fdi.htm',
        report_type=report_type,
        from_year=from_year,
        to_year=to_year,
        from_month=from_month, to_month=to_month)

    return df

def credit_report(report_type, from_year, to_year, from_month=None, to_month=None):
    # Sử dụng hàm để lấy dữ liệu
    df = macroeconomics_report(
        url='https://finance.vietstock.vn/du-lieu-vi-mo/51/tin-dung.htm',
        report_type=report_type,
        from_year=from_year,
        to_year=to_year,
        from_month=from_month, to_month=to_month)

    return df

def industries_company():
    
    url_1 = 'https://api.vietcap.com.vn/data-mt/graphql'
    payload = "{\"query\":\"{ CompaniesListingInfo { ticker organName icbName2 icbName3 icbName4 } }\",\"variables\":{}}"

    response_1 = requests.post(url_1, headers=get_headers(), data=payload)
    json_data = response_1.json()
    df = pd.DataFrame(json_data['data']['CompaniesListingInfo'])
    data_1 = df.rename(columns={'ticker': 'symbol'})

    url_2 = 'https://mt.vietcap.com.vn/api/price/symbols/getAll'
    response_2 = requests.post(url_2, headers=get_headers())
    json_data = response_2.json()
    data_2 = pd.DataFrame(json_data)

    data = pd.merge(data_1, data_2[['symbol', 'board']], on='symbol', how='left')
    new_column_order = ['symbol', 'board', 'organName', 'icbName2', 'icbName3', 'icbName4']
    data = data[new_column_order]
    return data

def company_overview(symbol):

    url = f'{base_url}/{analysis_url}/v1/ticker/{symbol}/overview'
    response = requests.get(url, headers=get_headers())
    data = response.json()
    df = pd.DataFrame(data, index=[0])
    df = df[['ticker', 'exchange', 'industry', 'companyType',
            'noShareholders', 'foreignPercent', 'outstandingShare', 'issueShare',
            'establishedYear', 'noEmployees',  
            'stockRating', 'deltaInWeek', 'deltaInMonth', 'deltaInYear', 
            'shortName', 'website', 'industryID', 'industryIDv2']]
    return df

def sub_company(symbol):
    url = f'https://iboard-api.ssi.com.vn/statistics/company/sub-companies?symbol={symbol}&language=vn&page=1&pageSize=999999'
    response = requests.get(url, headers=get_headers())
    response.raise_for_status()  # Kiểm tra nếu có lỗi HTTP

    json_data = response.json()
    df = pd.DataFrame(json_data['data'])
    df.drop(columns=['parentSymbol', 'roleId', 'parentCompanyName'], inplace=True)
    df.rename(columns={
        "childCompanyName": "Công ty con",
        "charterCapital": "Vốn điều lệ",
        "percentage": "Phần trăm",
        "roleName": "Vai trò",
        "childSymbol": "Mã cổ phiếu"},
        inplace=True)

    df = df.iloc[:, [1, 0, 2, 3, 4]]  # Chọn lại các cột theo thứ tự mong muốn
    return df

def share_holder(symbol):
    url = f'https://iboard-api.ssi.com.vn/statistics/company/shareholders?symbol={symbol}&language=vn&page=1&pageSize=999'
    response = requests.get(url, headers=get_headers())
    data = response.json()['data']
    df = pd.DataFrame(data)
    df.iloc[:,[1,0,2,3,4,5,6]]
    return df

# Thống kê mô tả đầy đủ
def descriptive_stats(rng):
    values = [cell or 0 for cell in rng]

    return {
        'mean': round(np.mean(values), 2),
        'standard_error':round(stats.tstd(values) / np.sqrt(np.count_nonzero(values)), 2),
        'median':round(float(np.median(values)), 2),
        'mode': round(stats.mode(values, axis=None, keepdims=False)[0], 2),  # can xem them vi co the mode co nhieu gia tri
        'std': round(stats.tstd(values), 2),
        'variance': round(stats.tstd(values) ** 2, 2),
        'kurtosis': round(float(stats.kurtosis(values, bias=False)), 2),
        'skewness': round(float(stats.skew(values, bias=False)), 2),
        'range': round(float(np.ptp(values)), 2),
        'max': round(np.max(values), 2),
        'min': round(np.min(values), 2),
        'sum': round(np.sum(values), 2),
        'count': round(np.count_nonzero(values), 2),
        'geometric_mean': round(float(gmean(values)), 2),
        'harmonic_mean': round(float(hmean(values)), 2),
        'average_deviation': round(float(np.mean(np.abs(values - np.mean(values)))), 2),
        'median_abs_deviation': round(float(stats.median_abs_deviation(values)), 2),
        'iqr': round(float(stats.iqr(values)), 2),
        '25%': round(np.percentile(values, 25), 2),
        '50%': round(np.percentile(values, 50), 2),
        '75%': round(np.percentile(values, 75), 2),
        'cv': round(stats.variation(values) * 100, 2),
        'Position Q1': round(((25 / 100) * (np.count_nonzero(values) + 1)), 2),
        'Position Q2': round(((50 / 100) * (np.count_nonzero(values) + 1)), 2),
        'Position Q3': round(((75 / 100) * (np.count_nonzero(values) + 1)), 2)
    }




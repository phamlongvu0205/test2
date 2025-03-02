from django.shortcuts import render
from django.http import HttpResponse
import io
import pandas as pd
import sys
from pathlib import Path
import io

# Import hàm price_stock từ file finance_df.py
from stock_app.static.finance_py.finance_df import *
from stock_app.static.finance_py.const import *

def gold(request):
    if request.method == "POST":
        fromdate = request.POST.get('from_date')
        todate = request.POST.get('to_date')
        action = request.POST.get('action')
        # Validate required fields
        if not fromdate or not todate:
            error_msg = 'Please fill in Symbol, From Date, and To Date!'
            return render(request, 'pages/gold.html', {
                'error': error_msg,
                'from_date': fromdate,
                'to_date': todate,
            })

        # Fetch stock data
        try:
            df = gold_sjc(fromdate, todate)
        except Exception as e:
            error_msg = f"Error fetching data: {str(e)}"
            return render(request, 'pages/gold.html', {
                'error': error_msg,
                'from_date': fromdate,
                'to_date': todate,
            })

        if action == "get_data":
            data_list = df.to_dict('records')
            return render(request, 'pages/gold.html', {
                'data': data_list,
                'from_date': fromdate,
                'to_date': todate,
            })

        elif action == "download":
            # Làm sạch dữ liệu DataFrame trước khi export
            df_clean = df.replace(r'\n|\r', ' ', regex=True)  # Xóa các ký tự xuống dòng
            df_clean = df_clean.applymap(lambda x: x.strip() if isinstance(x, str) else x)  # Xóa khoảng trắng dư

            # Tạo file CSV
            response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
            response['Content-Disposition'] = 'attachment; filename="gold_data.csv"'

            # Ghi dữ liệu vào file CSV
            output = io.StringIO()
            df_clean.to_csv(
                path_or_buf=output,
                index=False,
                sep=",",  # Sử dụng dấu phẩy là chuẩn CSV
                encoding="utf-8-sig"
            )
            
            # Ghi dữ liệu từ StringIO vào HttpResponse
            response.write(output.getvalue())
            return response
    return render(request, 'pages/gold.html')

def get_stock_data(request):
    if request.method == "POST":
        symbol = request.POST.get('symbol')
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        file_from_date = request.POST.get('file_from_date')
        action = request.POST.get('action')
        # Validate required fields
        if not symbol or not from_date or not to_date:
            error_msg = 'Please fill in Symbol, From Date, and To Date!'
            return render(request, 'pages/home.html', {
                'error': error_msg,
                'symbol': symbol,
                'from_date': from_date,
                'to_date': to_date,
            })

        # Fetch stock data
        try:
            df = price_stock(symbol, from_date, to_date)
        except Exception as e:
            error_msg = f"Error fetching data: {str(e)}"
            return render(request, 'pages/home.html', {
                'error': error_msg,
                'symbol': symbol,
                'from_date': from_date,
                'to_date': to_date,
            })

        # No data found
        if df.empty:
            error_msg = f'No data found for {symbol} in the given date range!'
            return render(request, 'pages/home.html', {
                'error': error_msg,
                'symbol': symbol,
                'from_date': from_date,
                'to_date': to_date,
            })

        if action == "get_data":
            data_list = df.to_dict('records')
            return render(request, 'pages/home.html', {
                'data': data_list,
                'symbol': symbol,
                'from_date': from_date,
                'to_date': to_date,
            })

        elif action == "download":
            # Làm sạch dữ liệu DataFrame trước khi export
            df_clean = df.replace(r'\n|\r', ' ', regex=True)  # Xóa các ký tự xuống dòng
            df_clean = df_clean.applymap(lambda x: x.strip() if isinstance(x, str) else x)  # Xóa khoảng trắng dư

            # Tạo file CSV
            response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
            response['Content-Disposition'] = 'attachment; filename="financial_data.csv"'

            # Ghi dữ liệu vào file CSV
            output = io.StringIO()
            df_clean.to_csv(
                path_or_buf=output,
                index=False,
                sep=",",  # Sử dụng dấu phẩy là chuẩn CSV
                encoding="utf-8-sig"
            )
            
            # Ghi dữ liệu từ StringIO vào HttpResponse
            response.write(output.getvalue())
            return response
    return render(request, 'pages/home.html')

def financial_statement(request):
    if request.method == "POST":
        symbol = request.POST.get('symbol')
        type = request.POST.get('type')
        year = request.POST.get('year')
        timely = request.POST.get('timely')
        action = request.POST.get('action')

        # Validate required fields
        if not symbol or not type or not year or not timely:
            error_msg = 'Please fill in all required fields: Symbol, Type, Year, and Timely!'
            return render(request, 'pages/fs.html', {
                'error': error_msg,
                'symbol': symbol,
                'type': type,
                'year': year,
                'timely': timely,
            })
        
        df = financial_report(symbol, type, year, timely)

        # No data found
        if df.empty:
            error_msg = f'No data found for {symbol} in the given date range!'
            return render(request, 'pages/fs.html', {
                'error': error_msg,
                'symbol': symbol,
                'type': type,
                'year': year,
                'timely': timely,
            })

        # Handle action: get_data
        if action == "get_data":
            data_list = df.to_dict('records')
            return render(request, 'pages/fs.html', {
                'data': data_list,
                'symbol': symbol,
                'type': type,
                'year': year,
                'timely': timely,
            })

        # Handle action: download
        elif action == "download":
            # Làm sạch dữ liệu DataFrame trước khi export
            df_clean = df.replace(r'\n|\r', ' ', regex=True)  # Xóa các ký tự xuống dòng
            df_clean = df_clean.applymap(lambda x: x.strip() if isinstance(x, str) else x)  # Xóa khoảng trắng dư

            # Tạo file CSV
            response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
            response['Content-Disposition'] = 'attachment; filename="financial_data.csv"'

            # Ghi dữ liệu vào file CSV
            output = io.StringIO()
            df_clean.to_csv(
                path_or_buf=output,
                index=False,
                sep=",",  # Sử dụng dấu phẩy là chuẩn CSV
                encoding="utf-8-sig"
            )
            
            # Ghi dữ liệu từ StringIO vào HttpResponse
            response.write(output.getvalue())
            return response

        # Invalid action
        else:
            error_msg = "Invalid action. Please select a valid action: Get Data or Download."
            return render(request, 'pages/fs.html', {
                'error': error_msg,
                'symbol': symbol,
                'type': type,
                'year': year,
                'timely': timely,
            })

    # Default GET request or no action
    return render(request, 'pages/fs.html')

# def forex(request):
#     if request.method == "POST":
#         fromdate = request.POST.get('from_date')
#         todate = request.POST.get('to_date')
#         action = request.POST.get('action')
#         # Validate required fields
#         if not fromdate or not todate:
#             error_msg = 'Please fill in Symbol, From Date, and To Date!'
#             return render(request, 'pages/forex.html', {
#                 'error': error_msg,
#                 'from_date': fromdate,
#                 'to_date': todate,
#             })

#         # Fetch stock data
#         try:
#             df = exchange_rate(fromdate, todate)
#         except Exception as e:
#             error_msg = f"Error fetching data: {str(e)}"
#             return render(request, 'pages/forex.html', {
#                 'error': error_msg,
#                 'from_date': fromdate,
#                 'to_date': todate,
#             })

#         if action == "get_data":
#             data_list = df.to_dict('records')
#             return render(request, 'pages/forex.html', {
#                 'data': data_list,
#                 'from_date': fromdate,
#                 'to_date': todate,
#             })

#         elif action == "download":
#             # Làm sạch dữ liệu DataFrame trước khi export
#             df_clean = df.replace(r'\n|\r', ' ', regex=True)  # Xóa các ký tự xuống dòng
#             df_clean = df_clean.applymap(lambda x: x.strip() if isinstance(x, str) else x)  # Xóa khoảng trắng dư

#             # Tạo file CSV
#             response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
#             response['Content-Disposition'] = 'attachment; filename="forex_data.csv"'

#             # Ghi dữ liệu vào file CSV
#             output = io.StringIO()
#             df_clean.to_csv(
#                 path_or_buf=output,
#                 index=False,
#                 sep=",",  # Sử dụng dấu phẩy là chuẩn CSV
#                 encoding="utf-8-sig"
#             )
            
#             # Ghi dữ liệu từ StringIO vào HttpResponse
#             response.write(output.getvalue())
#             return response
#     return render(request, 'pages/forex.html')

def forex(request):
    if request.method == "POST":
        fromdate = request.POST.get('from_date')
        todate = request.POST.get('to_date')
        search_currency = request.POST.get('search_currency', '').strip()
        action = request.POST.get('action')

        if not fromdate or not todate:
            error_msg = 'Please fill in From Date and To Date!'
            return render(request, 'pages/forex.html', {
                'error': error_msg,
                'from_date': fromdate,
                'to_date': todate,
                'search_currency': search_currency,
            })

        # Fetch data
        try:
            df = exchange_rate(fromdate, todate)

            # Nếu có tìm kiếm nhiều Currency Code
            if search_currency:
                # Tách các mã Currency Code thành danh sách
                currency_list = [code.strip().upper() for code in search_currency.split(",")]
                # Lọc các hàng trong DataFrame theo danh sách Currency Code
                df = df[df['Currency Code'].isin(currency_list)]
        except Exception as e:
            error_msg = f"Error fetching data: {str(e)}"
            return render(request, 'pages/forex.html', {
                'error': error_msg,
                'from_date': fromdate,
                'to_date': todate,
                'search_currency': search_currency,
            })

        if action == "get_data":
            data_list = df.to_dict('records')
            return render(request, 'pages/forex.html', {
                'data': data_list,
                'from_date': fromdate,
                'to_date': todate,
                'search_currency': search_currency,
            })

        elif action == "download":
            # Làm sạch dữ liệu DataFrame trước khi export
            df_clean = df.replace(r'\n|\r', ' ', regex=True)
            df_clean = df_clean.applymap(lambda x: x.strip() if isinstance(x, str) else x)

            # Tạo file CSV
            response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
            response['Content-Disposition'] = 'attachment; filename="forex_data.csv"'

            # Ghi dữ liệu vào file CSV
            output = io.StringIO()
            df_clean.to_csv(
                path_or_buf=output,
                index=False,
                sep=",", 
                encoding="utf-8-sig"
            )
            response.write(output.getvalue())
            return response
    return render(request, 'pages/forex.html')

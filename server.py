#!/usr/bin/env python

'''
HTTP(S) server for serving GET requests for static files in the 'www' directory
multi-threaded to allow for serving multiple requests simultaneously
port is passed in as first argument from command line
print a timestamped one-line log output for each request/reply pair
supports common MIME types and HTTP error codes

For further optimization, replace the threads with a thread pool to decrease the overhead of thread creation/destruction
For security, the server does not display directory contents, run executable files, or private files

HTTP Status Codes:
1xx: uncommon
2xx: okay
3xx: redirection
4xx: client error
5xx: server error

the ones implemented are:
200: okay
403: forbidden
404: not found
405: method not allowed
500: internal server error
'''

import sys # for receiving port number from command line
import socket
import signal # to shutdown server on Ctrl+C
import time # for displaying current time in log
import threading
import thread
import traceback
import os
import mimetypes
import urllib
import ssl

class HTTPServer:
    def __init__(self,port,secure):
        self.host = '' # any hostname
        self.port = port
        self.secure = secure
        self.directory = 'www' # folder to use for serving files out of
        
    def start_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.host, self.port))
            print "HTTP(S) server listening for connections on port " + str(self.port)
        except:
            print "Unable to acquire port " + str(self.port) + " - please try another"
            self.stop_server()
        self.wait_loop()
        
    def stop_server(self, sig_num=0, stack_frame=None):
        try:
            print "Stopping the server"
            self.socket.shutdown(socket.SHUT_RDWR)
        except:
            print "Socket was previously shut down"
        sys.exit(1)
        
    def wait_loop(self):
        while True: # run forever until Ctrl+C
            self.socket.listen(5) # 5 is usually the max. number of queued connections possible
            sock, addr = self.socket.accept()
            if self.secure==True:
                sock = ssl.wrap_socket(sock, certfile='server.pem', server_side=True,ssl_version=ssl.PROTOCOL_TLSv1)
            thread.start_new_thread(self.serve_request, (sock, addr))
        
    def serve_request(self, sock, addr):
        try:
            filename = self.parse_GET(sock) # parse GET
        except:
            # not a GET request
            response = self.generate_headers(405,0,'') + self.generate_error_HTML(405) # send headers + file content
            sock.send(response)
            sock.close()
            print self.timestamp() + ": received non-GET request.  Response: 405"
            return # to prevent continued execution
        try:
            handler, file_size, status = self.load_file(filename) # find file & return data
            header = self.generate_headers(status,file_size,filename)
            sock.send(header)
            if status==200: # data is a file-handler
                while True:
                    # read the file in 1 MB chunks to avoid overloading memory
                    data = handler.read(1024)
                    if not data: # end of file
                        break
                    sock.send(data)
                handler.close()
            else:
                sock.send(handler) # send the HTML
            sock.close()
        except:
            response = self.generate_headers(500,0,'') + self.generate_error_HTML(500) # send headers + file content
            sock.send(response)
            sock.close()
            #traceback.print_exc(file=sys.stdout)
        print self.timestamp() + ": received request for " + filename + ".  Response: " + str(status)
    
    # utility functions        
    
    def MIME_types(self,filename):
        file_type = mimetypes.guess_type(filename)[0]
        return file_type if file_type!=None else "unknown"
    
    def parse_GET(self, sock):
        line = sock.makefile('rw').readline() # reads first line
        request = line.split() # list of space-delimited words in first line
        if request[0]=="GET":
            # GET request
            filename = request[1] # typically /index.html
            filename = filename.split('?')[0] # discard trailing URL args
            filename = urllib.unquote(filename) # in case file has a space in its name, converts %20 to ' '
            return filename
        else:
            # not a GET request
            raise
        
    def load_file(self, filename):
        if filename=="/":
            filename="/index.html"
        full_path = self.directory + filename
        try:
            if os.path.exists(full_path)==False: # file doesn't exist
                html = self.generate_error_HTML(404)
                return html, len(html), 404
            if os.access(full_path, os.R_OK) and os.access(full_path, os.X_OK)==False: # have read access, is not executable
                file = open(full_path, 'rb') # binary mode
                size = os.path.getsize(os.getcwd() + '/' + full_path)
                return file, size, 200
            else:
                # access forbidden
                html = self.generate_error_HTML(403)
                return html, len(html), 403
        except:
            raise
            
    def timestamp(self):
        return time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
    
    def generate_error_HTML(self,code):
        pre_html = "<html><head><title>Oops!</title></head><body><p>"
        post_html = "Please try the <a href='/index.html'>homepage</a> while we try to fix this problem.</p></body></html>"
        if code==404:
            msg = "The page you requested was not found.  "
        elif code==403:
            msg = "You do not have access to that file on the server.  "
        elif code==405:
            msg = "Please send a valid GET request.  "
        elif code==500:
            msg = "The server has made an error.  "
        return pre_html + msg + post_html
        
    def generate_headers(self,code,file_size,filename):
        headers = {}
        if code==200:
            header_status = "HTTP/1.1 200 OK"
            headers["Content-Type"] = self.MIME_types(filename)
            headers["Content-Length"] = repr(file_size) # in bytes
        elif code==403:
            header_status = "HTTP/1.1 403 Forbidden"
        elif code==404:
            header_status = "HTTP/1.1 404 Not Found"
        elif code==405:
            header_status = "HTTP/1.1 405 Method Not Allowed"
        elif code==500:
            header_status = "HTTP/1.1 500 Internal Server Error"
        headers["Date"] = self.timestamp()
        headers["Server"] = "Python HTTP GET server/0.1"
        headers_collated = ""
        for key, value in headers.iteritems():
            headers_collated += key + ": " + str(value) + "\n"
        header = header_status + "\n" + headers_collated + '\n'
        return header

if __name__ == '__main__':
    if sys.argv[1:]:
        port = int(sys.argv[1])
    else:
        port = 8000 # default port if none specified on command line
    server = HTTPServer(port,False) # port, turn SSL on
    signal.signal(signal.SIGINT, server.stop_server)
    server.start_server()